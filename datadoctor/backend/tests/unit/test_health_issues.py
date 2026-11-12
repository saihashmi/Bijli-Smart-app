"""Issue detection (SPEC §10.1) and the Data Health Score (SPEC §10.2), checked against hand counts."""

import pandas as pd
import pytest

from app.services.profiling.health import finalize, health_score
from app.services.profiling.profile import dataset_profile


def issues_of(df, **context):
    p = dataset_profile(df, context=context)
    return p, {(i["code"], i["column"]): i for i in p["issues"]}


def test_health_score_matches_hand_calculation():
    df = pd.DataFrame({"Qty": [1, 2, 2, None], "City": ["Lahore", "Lahore", "Lahore", "lahore "]}, dtype=object)
    p = dataset_profile(df)
    h = health_score(p)
    # C = 1 - 1/8 = 0.875 · U = 1 - 1/4 = 0.75 · T = (1 + 1)/2 = 1
    # F: Qty 3/3 = 1; City: "lahore " has edge spaces and is a variant of "Lahore" → 3/4 = 0.75 → F = 0.875
    # Score = 100 × (0.35×0.875 + 0.20×0.75 + 0.25×1 + 0.20×0.875) = 88.125 → 88
    comps = {c["key"]: c["value"] for c in h["components"]}
    assert comps == {"completeness": 0.875, "uniqueness": 0.75, "type_consistency": 1.0, "format_consistency": 0.875}
    assert h["score"] == 88 and h["band"] == "Good"
    assert "does not check whether values are true" in " ".join(h["limitations"])


def test_no_score_for_empty_sheet():
    assert health_score(dataset_profile(pd.DataFrame({"a": []}, dtype=object))) is None


def test_perfect_data_scores_100():
    df = pd.DataFrame({"n": [1, 2, 3], "city": ["Lahore", "Karachi", "Multan"]}, dtype=object)
    assert health_score(dataset_profile(df))["score"] == 100


@pytest.mark.parametrize(
    ("values", "file_type", "expected"),
    [
        (["1250.5", "900", "12"], "csv", None),  # plain numbers in a CSV are normal
        (["1250.5", "Rs 1,000", "(5)"], "csv", 2),
        (["1250.5", "900", "12"], "xlsx", 3),  # text in an Excel cell is a real problem
    ],
)
def test_numbers_stored_as_text(values, file_type, expected):
    _, issues = issues_of(pd.DataFrame({"Amount": values}, dtype=object), file_type=file_type)
    got = issues.get(("Q08", "Amount"))
    assert (got["affected_rows"] if got else None) == expected


def test_whitespace_variants_and_repeated_spaces():
    df = pd.DataFrame({"City": ["Lahore", "Lahore", " lahore", "LAHORE", "Karachi", "Port  Qasim"]}, dtype=object)
    _, issues = issues_of(df)
    assert issues[("Q07", "City")]["affected_rows"] == 2  # " lahore", "LAHORE" → "Lahore"
    assert issues[("Q05", "City")]["affected_rows"] == 1
    assert issues[("Q05", "City")]["severity"] == "medium"  # it splits a category
    assert issues[("Q06", "City")]["affected_rows"] == 1


def test_variant_tie_prefers_clean_title_case():
    df = pd.DataFrame({"City": [" lahore", "LAHORE", "Lahore"]}, dtype=object)
    _, issues = issues_of(df)
    assert "“Lahore” (1)" in issues[("Q07", "City")]["examples"][0]["value"].split(" / ")[0]


def test_outliers_are_flagged_not_removed():
    values = list(range(10, 40)) + [10_000]
    _, issues = issues_of(pd.DataFrame({"Amount": values}, dtype=object))
    q13 = issues[("Q13", "Amount")]
    assert q13["affected_rows"] == 1 and q13["severity"] == "low"
    assert q13["examples"][0] == {"row": 32, "value": "10000"}  # header on row 1 → 31st data row is row 32


def test_personal_identifiers_by_pattern_and_name_with_masked_examples():
    df = pd.DataFrame(
        {
            "Ref": ["35202-1234567-1", "42101-7654321-3", "61101-1111111-5", "37405-2222222-9"],
            "Customer Name": ["Ayesha", "Bilal", "Sana", "Usman"],
            "Product name": ["A", "B", "C", "D"],
        },
        dtype=object,
    )
    _, issues = issues_of(df)
    assert ("Q16", "Ref") in issues and ("Q16", "Customer Name") in issues
    assert ("Q16", "Product name") not in issues
    example = issues[("Q16", "Ref")]["examples"][0]["value"]
    assert example.startswith("35") and "1234567" not in example


def test_dataset_level_issues_and_examples_use_spreadsheet_rows():
    df = pd.DataFrame({"a": [1, 1, None], "b": ["x", "x", None]}, dtype=object)
    _, issues = issues_of(df, header_row=2)  # header on spreadsheet row 3 → data starts on row 4
    assert issues[("Q01", None)]["affected_rows"] == 1
    assert issues[("Q01", None)]["examples"][0]["row"] == 5
    assert issues[("Q04", None)]["examples"][0]["row"] == 6


def test_finalize_hides_resolved_issues():
    df = pd.DataFrame({"CNIC": ["35202-1234567-1"] * 3 + ["42101-7654321-3"], "D": ["03/04/2026"] * 4}, dtype=object)
    p = dataset_profile(df)
    codes = {(i["code"], i["column"]) for i in p["issues"]}
    assert {("Q16", "CNIC"), ("Q11", "D")} <= codes
    out = finalize(p, sensitive=["CNIC"], date_rules={"columns": {"D": "DMY"}})
    codes = {(i["code"], i["column"]) for i in out["issues"]}
    assert ("Q16", "CNIC") not in codes and ("Q11", "D") not in codes
    # Resolving the ambiguous dates also raises format consistency for that column.
    assert out["health"]["score"] > finalize(p, [], {})["health"]["score"]
