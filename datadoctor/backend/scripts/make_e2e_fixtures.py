"""Write the synthetic spreadsheets used by the Playwright tests (frontend/tests/e2e/fixtures).

cd backend && .venv/bin/python scripts/make_e2e_fixtures.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.fixtures import builders as fx  # noqa: E402

OUT = ROOT.parent / "frontend" / "tests" / "e2e" / "fixtures"

FILES = {
    "multi_sheet_sales.xlsx": fx.xlsx_multi_sheet,
    "password_protected.xlsx": fx.encrypted_xlsx,
    "legacy_claims.xls": fx.xls_legacy,
}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, build in FILES.items():
        (OUT / name).write_bytes(build())
        print("wrote", OUT / name)
