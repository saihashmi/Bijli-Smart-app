# DataDoctor AI

**From messy data to meaningful decisions.** Upload an Excel or CSV file, see exactly what is wrong with it, fix it step by step with a full audit trail, explore it on a dashboard, ask questions in plain language, and export the cleaned data and a report.

Upload → Profile → Clean → Analyze → Visualize → Export

> **Status: MVP in development, local single-user mode.** It is not ready for public internet hosting: there is no user login yet (see [Security](#security-and-privacy)).

## What it does

| Screen | What you get |
|---|---|
| **Upload Studio** | `.xlsx`, `.xls`, `.csv` up to 20 MB. Content is checked (not just the extension), macros and formulas are never run, you pick the worksheet and header row from a raw preview. |
| **Data Health Center** | A 0–100 Data Health Score with its formula and breakdown, every issue with exact row counts, a missing-value map, and the affected rows one click away. |
| **Cleaning Studio** | 17 rule-based fixes. Each one is previewed on the full data before you apply it. Undo, reset, before/after comparison and a complete history. The original file is never changed. |
| **Dashboard Studio** | An automatic first dashboard built from column types (with the reason for every chart), a widget editor that only offers valid combinations, filters, drill-down, three themes, chart image download. |
| **AI Analyst** | Questions are mapped to one of 14 fixed calculations and computed on your data. Works with no AI key. With a Groq key, AI may choose the calculation and write an explanation, which is checked against the computed result and discarded if it adds anything. |
| **Export Center** | Excel workbook (cleaned data, quality report, audit log, statistics) and a PDF report, built from the same figures the app shows. |

### Principles the code enforces

- **Nothing is invented.** Every figure is calculated from the uploaded file by the server. The browser and the AI never calculate.
- **Nothing is guessed.** An ambiguous date such as `03/04/2026` is never assigned to a month until you say how to read it. Missing or non-numeric cells are never treated as zero; they are left out and the count is shown.
- **Nothing is silently changed.** The original upload is kept as it is. Every cleaning step is previewed, recorded and reversible.

## Run it locally

Requirements: Python 3.12+ and Node.js 20+.

```bash
cd datadoctor
cp .env.example .env        # optional: the defaults work
make setup                  # creates backend/.venv and installs frontend packages

make backend                # terminal 1: API on http://127.0.0.1:8000
make frontend               # terminal 2: app on http://localhost:3000
```

Open http://localhost:3000. Data is stored under `STORAGE_DIR` (default `backend/storage`): uploads, working snapshots, exports and a SQLite file with metadata only.

### Optional: AI explanations

Set `GROQ_API_KEY` in `.env` and restart the backend. Without it the AI Analyst uses its built-in interpreter and guided builder, and every calculation still works. Using Groq may cost money on your Groq account, and sends the items listed under [What leaves your computer](#what-leaves-your-computer).

## Tests and checks

```bash
make test     # backend (pytest) and frontend unit tests (vitest)
make lint     # ruff, eslint, TypeScript
make audit    # known-vulnerability scan of Python and npm dependencies
make e2e      # browser tests (Playwright); needs both servers running
```

The browser tests run at four widths (375, 768, 1280, 1440) and include an automated accessibility scan (axe, WCAG 2.1 A/AA) of every screen in light and dark themes. Figures on the dashboard, in AI answers and in exports are tested against hand-counted values and independent pandas calculations.

## Configuration

All settings are environment variables; see [`.env.example`](.env.example). The most relevant:

| Variable | Default | Meaning |
|---|---|---|
| `MAX_UPLOAD_MB` | 20 | Upload size limit (rebuild the frontend after changing it) |
| `RETENTION_DAYS` | 7 | Uploaded data is deleted automatically after this many days |
| `PROCESS_TIMEOUT_S` / `WORKER_MEMORY_MB` | 60 / 2048 | Limits for parsing, profiling, cleaning and exports |
| `DISPLAY_TIMEZONE` | Asia/Karachi | Default time zone for timestamps (changeable in Settings) |
| `SECRET_KEY` | generated | Signs the workspace cookie and download links |
| `GROQ_API_KEY`, `GROQ_MODEL` | empty | Optional AI provider |

## Security and privacy

- **Local mode only.** A signed browser cookie keeps the data of different browsers apart. It is not authentication. **Do not expose this app to the public internet with private data until real login and per-user isolation are added.**
- Uploads are validated by content, size-limited, zip-bomb-checked and stored under generated names. Macros and formulas are never executed. Password-protected files are refused with a clear message.
- Exported text that a spreadsheet could read as a formula (`=`, `+`, `-`, `@`, tab, carriage return at the start) is neutralised.
- Exports can be downloaded only from the browser that created them, through a link that is valid for 10 minutes; files are deleted after 24 hours.
- Error messages never include stack traces or submitted values. Logs do not contain cell contents.
- Heavy work runs in a separate process with a time and memory limit, so one bad file cannot hang the server.
- No claim of compliance with any regulation (GDPR, HIPAA or others) is made. That needs a review this project has not had.

### What leaves your computer

Without a Groq key: **nothing.** With a key, only this is sent to Groq, and only when you ask the AI Analyst a typed question:

- your question;
- column names and types (or aliases such as `col_3` if you turn off name sharing in Settings); columns you mark as sensitive are never listed;
- for an explanation, the already computed answer (a few aggregated figures and group labels). Answers that use a sensitive column are never sent.

Rows, cell values and file names are never sent.

## Known limits

- Up to 1,000,000 rows, 500 columns and 20,000,000 cells per sheet (configurable).
- Health scoring measures structure (missing values, duplicates, consistent types and formats). It cannot tell whether a number is *true*.
- Recommendations use column types only. They do not understand what a column means.
- The PDF report draws bar, line and histogram charts; other widget types are listed, not drawn. Its built-in fonts cover Latin text only.
- Rate limits and caches are in-memory and assume a single server process.
- The Groq integration is tested against a simulated provider; it has not been exercised against the live service in this repository's test environment.

## Project layout

```
datadoctor/
  backend/    FastAPI, pandas, SQLAlchemy/Alembic, OpenPyXL, ReportLab
    app/routers/      HTTP API
    app/services/     ingest · profiling · cleaning · analytics · analyst · reports · storage
    tests/            unit and API tests
  frontend/   Next.js, TypeScript, Tailwind, Recharts, React Three Fiber (landing page only)
    src/app/          pages
    src/components/   one folder per screen
    tests/            unit and browser tests
  SPEC.md · PLAN.md · DESIGN_SPEC.md · UI_PLAN.md    what was agreed and why
  CLAUDE.md                                          working notes, decisions, known issues
```
