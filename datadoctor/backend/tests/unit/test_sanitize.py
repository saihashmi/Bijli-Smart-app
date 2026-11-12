import pytest

from app.services.ingest.files import sanitize_filename


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("report.xlsx", "report.xlsx"),
        ("../../etc/passwd.csv", "passwd.csv"),
        ("C:\\Users\\me\\data.csv", "data.csv"),
        ("bad\x00name\x1b.csv", "badname.csv"),
        ("  spaced   out  .csv", "spaced out .csv"),
        ("", "upload"),
        (None, "upload"),
        ("...", "upload"),
    ],
)
def test_sanitize_filename(raw, expected):
    assert sanitize_filename(raw) == expected
