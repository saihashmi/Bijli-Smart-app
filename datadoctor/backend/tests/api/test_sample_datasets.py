"""M14: the five synthetic sample datasets go through the whole product, with figures checked independently."""

from pathlib import Path

import pytest

SAMPLES = Path(__file__).parents[3] / "sample-data"

# file, header row, rows, issue codes that must be found, (column, expected total computed independently below)
CASES = [
    ("sales_orders.xlsx", 0, 603, {"Q01", "Q03", "Q08", "Q10", "Q11"}),
    ("clinic_visits.xlsx", 0, 450, {"Q03", "Q12", "Q13", "Q16"}),
    ("hr_employees.csv", 0, 380, {"Q03", "Q07", "Q08"}),
    ("inventory_stock.xlsx", 2, 320, {"Q04", "Q14"}),
    ("survey_responses.csv", 0, 500, {"Q03", "Q09"}),
]


def _open(client, name, header_row):
    ds = client.post("/api/uploads", files={"file": (name, (SAMPLES / name).read_bytes())})
    assert ds.status_code == 201, ds.text
    sess = client.post(f"/api/datasets/{ds.json()['id']}/sessions", json={"sheet_index": 0, "header_row": header_row})
    assert sess.status_code == 201, sess.text
    return sess.json()["id"]


@pytest.mark.parametrize("name,header_row,rows,codes", CASES, ids=[c[0] for c in CASES])
def test_sample_runs_through_every_stage(client, name, header_row, rows, codes):
    sid = _open(client, name, header_row)

    profile = client.get(f"/api/sessions/{sid}/profile").json()
    assert profile["rows"] == rows
    assert 0 <= profile["health"]["score"] <= 100
    found = {i["code"] for i in profile["issues"]}
    assert codes <= found, f"missing {codes - found}; found {sorted(found)}"
    for issue in profile["issues"]:  # every listed issue can show its rows (or says why not)
        res = client.get(f"/api/sessions/{sid}/issues/{issue['id']}/rows?limit=5")
        assert res.status_code in (200, 422), (issue["id"], res.text)
        if res.status_code == 200:
            assert res.json()["total"] == issue["affected_rows"]

    # every recommended widget and every suggested question works on this data
    rec = client.get(f"/api/sessions/{sid}/analytics/recommendations").json()
    widgets = rec["kpis"] + rec["charts"]
    out = client.post(f"/api/sessions/{sid}/analytics/query", json={"queries": [w["query"] for w in widgets]}).json()
    assert all(r["ok"] for r in out["results"]), [r for r in out["results"] if not r["ok"]]
    assert out["results"][0]["result"]["total"]["value"] == rows
    for tip in client.get(f"/api/sessions/{sid}/analyst/suggestions").json()["suggestions"]:
        answer = client.post(
            f"/api/sessions/{sid}/analyst/ask", json={"operation": tip["operation"], "params": tip["params"]}
        )
        assert answer.json()["status"] == "answered", (tip, answer.text)

    # a cleaning step, then both exports
    step = client.post(
        f"/api/sessions/{sid}/cleaning/apply", json={"operation_type": "trim_whitespace", "parameters": {}}
    )
    assert step.status_code in (200, 422), step.text  # 422 = nothing to trim in this file
    for kind in ("xlsx", "pdf"):
        job = client.post(f"/api/sessions/{sid}/exports", json={"type": kind}).json()
        assert job["status"] == "done", job
        assert client.get(job["download_url"]).status_code == 200


def test_sales_totals_match_an_independent_calculation(client):
    """Recompute from the generator's own rules, without the app's parser."""
    import random

    r = random.Random(11)
    prices = {"Solar Panel": 18500, "Inverter": 12000, "Battery": 7800, "Wiring Kit": 950, "Meter": 3200}
    amounts = []
    for i in range(600):
        r.randrange(540)
        product = r.choice(list(prices))
        units = r.randint(1, 24)
        r.choices(["a"] * 5, weights=[38, 27, 15, 8, 12])
        amounts.append(None if i % 97 == 0 else units * prices[product])  # text amounts ("Rs 12,000") still count
        r.choices(["a"] * 3, weights=[3, 5, 2])
        r.choices(["a"] * 2, weights=[8, 2])
    amounts += [amounts[5], amounts[50], amounts[500]]
    expected = sum(a for a in amounts if a is not None)
    used = sum(1 for a in amounts if a is not None)

    sid = _open(client, "sales_orders.xlsx", 0)
    q = {"kind": "aggregate", "measure": {"agg": "sum", "column": "Amount"}}
    res = client.post(f"/api/sessions/{sid}/analytics/query", json={"queries": [q]}).json()["results"][0]["result"]
    assert res["total"] == {"value": expected, "n": used}
    assert res["meta"]["measure_missing"] == len(amounts) - used

    # removing the three duplicate rows changes the total by exactly their amounts
    client.post(
        f"/api/sessions/{sid}/cleaning/apply",
        json={"operation_type": "remove_exact_duplicates", "parameters": {}, "confirm": True},
    )
    after = client.post(f"/api/sessions/{sid}/analytics/query", json={"queries": [q]}).json()["results"][0]["result"]
    assert after["total"]["value"] == expected - sum(a or 0 for a in (amounts[5], amounts[50], amounts[500]))


def test_inventory_needs_the_right_header_row(client):
    wrong = _open(client, "inventory_stock.xlsx", 0)
    cols = client.get(f"/api/sessions/{wrong}/analytics/fields").json()["fields"]
    assert cols[0]["name"].startswith("Warehouse stock list")  # the title row taken as a header: visibly wrong
    right = _open(client, "inventory_stock.xlsx", 2)
    names = [f["name"] for f in client.get(f"/api/sessions/{right}/analytics/fields").json()["fields"]]
    assert names[:3] == ["SKU", "Item", "Category"] and "On Hand" in names
    neg = {
        "kind": "aggregate",
        "measure": {"agg": "count"},
        "filters": [{"op": "range", "column": "On Hand", "max": -1}],
    }
    res = client.post(f"/api/sessions/{right}/analytics/query", json={"queries": [neg]}).json()["results"][0]["result"]
    assert res["total"]["value"] == len([i for i in range(320) if i % 47 == 0])


def test_survey_formula_like_comment_stays_text_everywhere(client):
    import io

    from openpyxl import load_workbook

    sid = _open(client, "survey_responses.csv", 0)
    job = client.post(f"/api/sessions/{sid}/exports", json={"type": "xlsx"}).json()
    wb = load_workbook(io.BytesIO(client.get(job["download_url"]).content))
    comments = {r[6].value for r in wb["Cleaned Data"].iter_rows(min_row=2)}
    assert "'=1+1 not a formula, just text" in comments and "=1+1 not a formula, just text" not in comments
    assert all(c.data_type != "f" for row in wb["Cleaned Data"].iter_rows() for c in row)


def test_bundled_samples_load_through_the_normal_pipeline_and_are_labelled(client, other_client):
    listed = client.get("/api/samples").json()
    assert [s["id"] for s in listed["samples"]] == ["sales", "clinic", "hr", "inventory", "survey"]
    assert "Synthetic" in listed["note"]
    for sample in listed["samples"]:
        res = client.post(f"/api/samples/{sample['id']}/load")
        assert res.status_code == 201, res.text
        body = res.json()
        assert "(synthetic sample)" in body["dataset"]["original_filename"]  # never passes as the user's own file
        sess = client.post(
            f"/api/datasets/{body['dataset']['id']}/sessions", json={"sheet_index": 0, "header_row": body["header_row"]}
        )
        assert sess.status_code == 201, sess.text
        assert client.get(f"/api/sessions/{sess.json()['id']}/profile").json()["rows"] == sample["rows"]
    assert len(client.get("/api/datasets").json()) == 5 and other_client.get("/api/datasets").json() == []
    for bad in ["nope", "..%2F..%2Fetc%2Fpasswd", "sales_orders.xlsx"]:
        assert client.post(f"/api/samples/{bad}/load").status_code == 404
