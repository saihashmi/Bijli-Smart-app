# Sample datasets (synthetic)

Every file here is **made up** by `generate.py` with fixed random seeds. No real person, company or transaction is described. Names, phone numbers and e-mail addresses are placeholders (`example.com`, `0300-555…`).

They are messy on purpose, in known ways, so you can try each part of DataDoctor AI:

| File | Rows | What to look for |
|---|---|---|
| `sales_orders.xlsx` | 603 | Amounts stored as text (`Rs 12,000`), missing amounts, ambiguous dates (`03/04/2025`), region spelling variants, 3 exact duplicate rows |
| `clinic_visits.xlsx` | 450 | Personal-data columns to mark as sensitive, impossible dates (`31/02/2026`), one extreme bill amount repeated, `N/A` values, yes/no spelled four ways |
| `hr_employees.csv` | 380 | Semicolon-separated, salaries with thousands separators, repeated employee IDs, department names in mixed case |
| `inventory_stock.xlsx` | 320 | A title row above the header (choose header row 3), an empty column, negative stock, a second sheet |
| `survey_responses.csv` | 500 | Only categories (nothing to total), blank answers, trailing spaces, day-first dates, a comment that starts with `=` |

Regenerate with `backend/.venv/bin/python sample-data/generate.py` (from `datadoctor/`). The data is identical every time (the seeds are fixed).
