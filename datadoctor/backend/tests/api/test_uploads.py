import pytest

from app.config import settings
from app.services.storage.paths import safe_path
from tests.fixtures import builders as fx

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def upload(client, name, data, ctype="application/octet-stream"):
    return client.post("/api/uploads", files={"file": (name, data, ctype)})


@pytest.fixture
def restore_settings():
    saved = dict(settings.__dict__)
    yield
    for k, v in saved.items():
        object.__setattr__(settings, k, v)


# ---------- valid files ----------


def test_xlsx_lists_all_sheets_with_visibility_and_formula_warnings(client):
    res = upload(client, "Sales Q2.xlsx", fx.xlsx_multi_sheet(), XLSX)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["file_type"] == "xlsx"
    assert body["original_filename"] == "Sales Q2.xlsx"
    sheets = {s["name"]: s for s in body["sheets"]}
    assert list(sheets) == ["Sales", "Lookup", "Internal", "Empty"]  # chart sheet omitted (no table data)
    assert sheets["Sales"]["visibility"] == "visible"
    assert (sheets["Sales"]["rows"], sheets["Sales"]["columns"]) == (5, 4)
    assert sheets["Sales"]["formula_cells_without_cache"] == 2
    assert sheets["Lookup"]["visibility"] == "hidden" and sheets["Lookup"]["selectable"]
    assert sheets["Internal"]["visibility"] == "very_hidden"
    assert sheets["Empty"]["selectable"] is False and "empty" in sheets["Empty"]["problem"]
    assert any("chart sheet" in w for w in body["warnings"])
    assert body["expires_at"] > body["uploaded_at"]


def test_xls_legacy_workbook(client):
    res = upload(client, "claims.xls", fx.xls_legacy())
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["file_type"] == "xls"
    sheets = {s["name"]: s for s in body["sheets"]}
    assert (sheets["Claims"]["rows"], sheets["Claims"]["columns"]) == (3, 3)
    assert sheets["Codes"]["visibility"] == "hidden"


@pytest.mark.parametrize(
    ("encoding", "delimiter", "expected_enc", "label"),
    [
        ("utf-8", ",", "utf-8", "comma"),
        ("utf-8-sig", ";", "utf-8-sig", "semicolon"),
        ("utf-16", "\t", "utf-16", "tab"),
        ("cp1252", "|", None, "pipe"),
    ],
)
def test_csv_encodings_and_delimiters(client, encoding, delimiter, expected_enc, label):
    rows = [["Name", "Café", "Amount"], ["Zoë", "Crème brûlée £", "1,250"], ["Bilal", "Karachi", "900"]]
    res = upload(client, "data.csv", fx.csv_bytes(encoding, delimiter, rows), "text/csv")
    assert res.status_code == 201, res.text
    body = res.json()
    csv = body["csv"]
    assert csv["delimiter_label"] == label
    if expected_enc:
        assert csv["encoding"] == expected_enc
    assert csv["replaced_characters"] == 0
    assert (body["sheets"][0]["rows"], body["sheets"][0]["columns"]) == (3, 3)
    peek = client.get(f"/api/datasets/{body['id']}/sheets/0/peek").json()
    assert peek["rows"][1] == ["Zoë", "Crème brûlée £", "1,250"]


def test_csv_with_quoted_newlines_counts_rows_correctly(client):
    data = b'id,note\n1,"line one\nline two"\n2,plain\n'
    body = upload(client, "notes.csv", data).json()
    assert (body["sheets"][0]["rows"], body["sheets"][0]["columns"]) == (3, 2)


def test_content_decides_type_when_extension_is_wrong(client):
    res = upload(client, "export.csv", fx.xlsx_simple())
    assert res.status_code == 201
    body = res.json()
    assert body["file_type"] == "xlsx"
    assert any("read as .xlsx" in w for w in body["warnings"])


def test_macros_are_reported_and_ignored(client):
    res = upload(client, "tool.xlsm", fx.with_macros(fx.xlsx_simple()))
    assert res.status_code == 201
    assert any("macros" in w and "never run" in w for w in res.json()["warnings"])


# ---------- rejected files ----------


@pytest.mark.parametrize(
    ("name", "data", "status", "code"),
    [
        ("empty.csv", b"", 422, "EMPTY_FILE"),
        ("report.pdf", b"%PDF-1.7 ...", 415, "UNSUPPORTED_FORMAT"),
        ("report.xlsx", b"%PDF-1.7 ...", 422, "WRONG_CONTENT"),
        ("letter.xlsx", fx.docx_like(), 422, "INVALID_EXCEL"),
        ("photo.csv", b"\x89PNG\r\n\x1a\n....", 422, "WRONG_CONTENT"),
        ("binary.csv", b"abc\x00\x01\x02def", 422, "WRONG_CONTENT"),
        ("notes.xlsx", b"just some text, not a workbook", 422, "WRONG_CONTENT"),
        ("no-extension", b"a,b\n1,2\n", 415, "UNSUPPORTED_FORMAT"),
    ],
)
def test_invalid_files_are_rejected_with_clear_codes(client, name, data, status, code):
    res = upload(client, name, data)
    assert res.status_code == status, res.text
    assert res.json()["error"]["code"] == code


def test_corrupted_xlsx(client):
    data = fx.xlsx_simple()
    res = upload(client, "broken.xlsx", data[: len(data) // 2])
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "CORRUPTED_FILE"


def test_password_protected_xlsx(client):
    res = upload(client, "secret.xlsx", fx.encrypted_xlsx())
    assert res.status_code == 422
    err = res.json()["error"]
    assert err["code"] == "PASSWORD_PROTECTED"
    assert "Remove the password" in err["message"]


def test_password_protected_xls_via_reader_error(client, monkeypatch):
    # No tool in this environment can write an encrypted .xls; simulate the reader's PasswordError instead.
    import python_calamine as pc

    from app.services.ingest import workbook

    def raise_password(_path):
        raise pc.PasswordError("password required")

    monkeypatch.setattr(workbook.pc.CalamineWorkbook, "from_path", staticmethod(raise_password))
    res = upload(client, "secret.xls", fx.xls_legacy())
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "PASSWORD_PROTECTED"


def test_oversized_upload_rejected(client, restore_settings):
    object.__setattr__(settings, "max_upload_mb", 1)
    res = upload(client, "big.csv", b"a,b\n" + b"1,2\n" * 400_000)
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_zip_bomb_guard(client, restore_settings):
    object.__setattr__(settings, "max_uncompressed_mb", 2)
    res = upload(client, "bomb.xlsx", fx.zip_bomb_like(3))
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "FILE_TOO_LARGE_UNCOMPRESSED"


def test_rejected_uploads_leave_no_files_behind(client):
    before = set((settings.storage_dir / "originals").iterdir())
    upload(client, "broken.xlsx", b"PK\x03\x04garbage")
    upload(client, "empty.csv", b"")
    assert set((settings.storage_dir / "originals").iterdir()) == before


def test_sheet_above_limits_is_not_selectable(client, restore_settings):
    object.__setattr__(settings, "max_rows", 2)
    body = upload(client, "data.xlsx", fx.xlsx_simple(rows=5)).json()
    sheet = body["sheets"][0]
    assert sheet["selectable"] is False and "row limit" in sheet["problem"]
    res = client.post(f"/api/datasets/{body['id']}/sessions", json={"sheet_index": 0})
    assert res.json()["error"]["code"] == "SHEET_NOT_USABLE"


# ---------- storage safety ----------


@pytest.mark.parametrize(
    ("name", "shown"),
    [
        ("../../etc/passwd.csv", "passwd.csv"),
        ("..\\..\\windows\\evil.csv", "evil.csv"),
        ("bad\x00name\x1b.csv", None),  # the HTTP client percent-encodes some control bytes
        ("   .csv", "csv"),
    ],
)
def test_malicious_filenames_are_sanitised_and_never_used_as_paths(client, name, shown):
    res = upload(client, name, fx.csv_bytes())
    if res.status_code != 201:  # a name like "csv" has no extension and is rejected: also safe
        assert res.json()["error"]["code"] == "UNSUPPORTED_FORMAT"
        return
    body = res.json()
    if shown is not None:
        assert body["original_filename"] == shown
    assert not any(ord(ch) < 32 for ch in body["original_filename"])
    assert "/" not in body["original_filename"] and "\\" not in body["original_filename"]
    stored = list((settings.storage_dir / "originals").glob(f"{body['id']}.*"))
    assert [p.name for p in stored] == [f"{body['id']}.csv"]


def test_long_filename_is_truncated_keeping_extension(client):
    body = upload(client, "a" * 400 + ".csv", fx.csv_bytes()).json()
    assert len(body["original_filename"]) <= 255
    assert body["original_filename"].endswith(".csv")


def test_original_is_stored_unchanged(client):
    data = fx.xlsx_multi_sheet()
    body = upload(client, "orig.xlsx", data).json()
    stored = safe_path("originals", f"{body['id']}.xlsx")
    assert stored.read_bytes() == data
