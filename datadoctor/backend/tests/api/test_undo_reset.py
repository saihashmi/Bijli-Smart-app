"""Milestone 8: undo, reset, replay of pruned versions, audit timeline, before/after comparison."""

import random

import pandas as pd
import pytest

from app.services.cleaning import engine
from app.services.cleaning.replay import KEEP_RECENT
from app.services.storage import snapshots
from tests.fixtures import builders as fx

ROWS = [
    ["Invoice", "Date", "City", "Amount", "Notes"],
    ["INV-1", "25/03/2026", " Lahore", "Rs 1,000", None],
    ["INV-2", "03/04/2026", "lahore", "(250)", "late"],
    ["INV-2", "03/04/2026", "lahore", "(250)", "late"],
    ["INV-3", "2026-04-05", "Karachi  West", "N/A", "  "],
    [None, None, None, None, None],
    ["INV-5", "31/02/2026", "KARACHI  WEST", "900", "x"],
    ["INV-6", "12-Jan-2025", "Islamabad", "1,250.5", None],
]

# A pool of operations that are valid on ROWS (some may change nothing at a given point: then they are skipped).
POOL = [
    ("trim_whitespace", {}, False),
    ("normalize_spaces", {}, False),
    ("standardize_case", {"columns": ["City"], "style": "title"}, False),
    ("remove_exact_duplicates", {}, True),
    ("remove_empty_rows", {}, True),
    ("convert_numeric", {"columns": ["Amount"]}, False),
    ("normalize_dates", {"column": "Date", "interpretation": "DMY"}, False),
    ("detect_missing", {}, False),
    ("flag_types", {"column": "Amount"}, False),
    ("handle_missing", {"column": "Notes", "strategy": "fixed", "value": "none given"}, True),
    ("rename_columns", {"mapping": {"Notes": "Remarks"}}, False),
]


def _session(client):
    ds = client.post("/api/uploads", files={"file": ("x.xlsx", fx.xlsx_from_rows(ROWS))}).json()
    s = client.post(f"/api/datasets/{ds['id']}/sessions", json={"sheet_index": 0}).json()
    return s["id"], s["dataset_id"]


def _current(sid, did, client):
    v = client.get(f"/api/sessions/{sid}").json()["version"]
    return v, snapshots.load(did, sid, v)


def _apply(client, sid, op, params, destructive):
    return client.post(
        f"/api/sessions/{sid}/cleaning/apply", json={"operation_type": op, "parameters": params, "confirm": destructive}
    )


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_random_sequences_undo_and_reset_are_exact(client, seed):
    rng = random.Random(seed)
    sid, did = _session(client)
    original = snapshots.load(did, sid, 0).copy()
    expected = [original]  # stack of expected states, built independently in memory
    for _ in range(9):
        if len(expected) > 1 and rng.random() < 0.3:
            assert client.post(f"/api/sessions/{sid}/cleaning/undo").status_code == 200
            expected.pop()
        else:
            op, params, destructive = rng.choice(POOL)
            if op == "rename_columns" and "Notes" not in expected[-1].columns:
                continue
            if op == "handle_missing" and "Notes" not in expected[-1].columns:
                continue
            _, _, result = engine.run(expected[-1], op, params, {"header_row": 0})
            res = _apply(client, sid, op, params, destructive)
            if result.affected_rows == 0:
                assert res.status_code == 422
                continue
            assert res.status_code == 200, res.text
            expected.append(result.df)
        _, got = _current(sid, did, client)
        pd.testing.assert_frame_equal(got, expected[-1])

    res = client.post(f"/api/sessions/{sid}/cleaning/reset", json={"confirm": True})
    if len(expected) == 1:
        assert res.status_code == 409
    else:
        assert res.status_code == 200
    v, got = _current(sid, did, client)
    assert v == 0
    pd.testing.assert_frame_equal(got, original)


def test_undo_rebuilds_pruned_versions_by_replay(client):
    sid, did = _session(client)
    steps = [
        ("trim_whitespace", {}, False),
        ("normalize_spaces", {}, False),
        ("convert_numeric", {"columns": ["Amount"]}, False),
        ("standardize_case", {"columns": ["City"]}, False),
        ("normalize_dates", {"column": "Date", "interpretation": "DMY"}, False),
    ]
    states = [snapshots.load(did, sid, 0).copy()]
    for op, p, d in steps:
        assert _apply(client, sid, op, p, d).status_code == 200
        states.append(snapshots.load(did, sid, client.get(f"/api/sessions/{sid}").json()["version"]).copy())
    kept = sorted(int(f.stem[1:]) for f in snapshots.snapshot_dir(did, sid).glob("v*.pkl"))
    assert kept == [0, 3, 4, 5]  # original + last KEEP_RECENT
    assert KEEP_RECENT == 3
    for expected in reversed(states[:-1]):
        assert client.post(f"/api/sessions/{sid}/cleaning/undo").status_code == 200
        _, got = _current(sid, did, client)
        pd.testing.assert_frame_equal(got, expected)  # v2 and v1 were rebuilt from the original


def test_nothing_to_undo_and_reset_needs_confirmation(client):
    sid, _ = _session(client)
    res = client.post(f"/api/sessions/{sid}/cleaning/undo")
    assert res.status_code == 409 and res.json()["error"]["code"] == "NOTHING_TO_UNDO"
    _apply(client, sid, "trim_whitespace", {}, False)
    res = client.post(f"/api/sessions/{sid}/cleaning/reset", json={})
    assert res.json()["error"]["code"] == "CONFIRMATION_REQUIRED"
    assert client.post(f"/api/sessions/{sid}/cleaning/reset", json={"confirm": True}).status_code == 200
    res = client.post(f"/api/sessions/{sid}/cleaning/reset", json={"confirm": True})
    assert res.json()["error"]["code"] == "ALREADY_ORIGINAL"


def test_timeline_records_every_step_in_order(client):
    sid, _ = _session(client)
    _apply(client, sid, "trim_whitespace", {}, False)
    _apply(client, sid, "remove_exact_duplicates", {}, True)
    client.post(f"/api/sessions/{sid}/cleaning/undo")
    client.put(f"/api/sessions/{sid}/sensitive-columns", json={"columns": ["City"]})
    client.post(f"/api/sessions/{sid}/cleaning/reset", json={"confirm": True})
    t = client.get(f"/api/sessions/{sid}/timeline").json()
    assert [e["type"] for e in t["events"]] == ["apply", "apply", "undo", "sensitive_columns", "reset"]
    assert t["events"][2]["details"]["operations"][0]["operation_type"] == "remove_exact_duplicates"
    assert [o["status"] for o in t["operations"]] == ["undone", "undone"]  # history is kept, never deleted
    assert t["current_version"] == 0


def test_undo_restores_settings_through_renames_and_removals(client):
    sid, _ = _session(client)
    client.put(f"/api/sessions/{sid}/sensitive-columns", json={"columns": ["Notes", "City"]})
    _apply(client, sid, "normalize_dates", {"column": "Date", "interpretation": "DMY"}, False)
    _apply(client, sid, "rename_columns", {"mapping": {"Notes": "Remarks"}}, False)
    _apply(client, sid, "remove_columns", {"columns": ["City"]}, True)
    prof = client.get(f"/api/sessions/{sid}/profile").json()
    assert prof["sensitive_columns"] == ["Remarks"]
    client.post(f"/api/sessions/{sid}/cleaning/undo")  # City comes back, still sensitive
    assert sorted(client.get(f"/api/sessions/{sid}/profile").json()["sensitive_columns"]) == ["City", "Remarks"]
    client.post(f"/api/sessions/{sid}/cleaning/undo")  # rename reversed
    assert sorted(client.get(f"/api/sessions/{sid}/profile").json()["sensitive_columns"]) == ["City", "Notes"]
    client.post(f"/api/sessions/{sid}/cleaning/undo")  # date reading no longer confirmed
    prof = client.get(f"/api/sessions/{sid}/profile").json()
    assert any(i["code"] == "Q11" for i in prof["issues"])


def test_compare_original_and_current(client):
    sid, _ = _session(client)
    _apply(client, sid, "trim_whitespace", {}, False)
    _apply(client, sid, "remove_exact_duplicates", {}, True)
    _apply(client, sid, "rename_columns", {"mapping": {"City": "Town"}}, False)
    cmp = client.get(f"/api/sessions/{sid}/compare?columns=Invoice&columns=Town").json()
    assert cmp["columns"] == [{"name": "Invoice", "original": "Invoice"}, {"name": "Town", "original": "City"}]
    assert cmp["removed_rows"] == 1
    rows = {r["row"]: r for r in cmp["rows"]}
    assert rows[2]["cells"][1] == {"before": " Lahore", "after": "Lahore", "changed": True, "new_column": False}
    assert rows[4]["removed"] is True  # the duplicate of INV-2 (spreadsheet row 4)
    every = client.get(f"/api/sessions/{sid}/compare?changed_only=false&limit=200").json()
    assert every["total"] == 7
    assert client.get(f"/api/sessions/{sid}/compare?columns=Nope").status_code == 422


def test_other_workspaces_cannot_undo(client, other_client):
    sid, _ = _session(client)
    _apply(client, sid, "trim_whitespace", {}, False)
    other_client.get("/api/settings")
    assert other_client.post(f"/api/sessions/{sid}/cleaning/undo").status_code == 404
    assert other_client.post(f"/api/sessions/{sid}/cleaning/reset", json={"confirm": True}).status_code == 404
    assert other_client.get(f"/api/sessions/{sid}/timeline").status_code == 404
