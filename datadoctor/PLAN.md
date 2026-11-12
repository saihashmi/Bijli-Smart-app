# DataDoctor AI — Implementation Plan (PLAN.md)

| | |
|---|---|
| Status | **Draft v1.0, awaiting product-owner approval** |
| Based on | SPEC.md v1.0 (approved 2026-11-12) |
| Branch | `ccr-47143d17-8h5n17` |
| Root | `datadoctor/` |

---

## 1. Technology choices, explained in plain language

| Layer | Choice | Why (non-technical) |
|---|---|---|
| Web interface | **Next.js 15 + TypeScript** | Widely used and well supported. TypeScript catches mistakes before users see them. |
| Styling and components | **Tailwind CSS v4 + shadcn/ui + Lucide icons** | shadcn/ui components are copied into our own code, not rented from a vendor, so they cost nothing and are fully customisable. The look stays consistent and accessible. |
| Font | **Inter, self-hosted** (`@fontsource-variable/inter`) | Inter as you asked, served from our own app so no request goes to Google and it works offline. |
| Charts | **Recharts 3** | Interactive charts for React, free. |
| Data tables | **TanStack Table + TanStack Virtual** | Big sheets stay smooth because only the rows on screen are drawn. Each page is fetched from the server, never the whole file. |
| Server | **Python 3.12 + FastAPI + Pydantic v2** | Python is the standard for data work. FastAPI checks every request automatically and documents the API. |
| Data processing | **Pandas + NumPy** | Industry standard, and calculations are well tested and reproducible. |
| Reading Excel | **python-calamine** (main), **OpenPyXL** (sheet details) | *A change from the suggested stack.* Calamine is a free, open-source reader that is **roughly 10× faster** than OpenPyXL on big files. It reads `.xlsx` and `.xls` with one library, returns saved formula results and never runs formulas or macros. OpenPyXL is still used for Excel **export** and the workbook-structure checks (hidden sheets, formulas without saved results). Without this change, a 20 MB workbook could take over a minute just to open. |
| Reading CSV | Pandas + `charset-normalizer` | Detects text encodings (Urdu/Windows exports) reliably. |
| Encrypted-file detection | `olefile` | Small, free. Recognises password-protected Excel files so we can explain the problem instead of crashing. |
| Database | **SQLite + SQLAlchemy 2 + Alembic** | SQLite is a single file and needs no database server: zero cost, nothing to run. Alembic keeps a versioned history of database changes. |
| Working copies of data | Files on disk (pickled DataFrames written only by our server) | Keeps the original's exact value types (dates vs text vs numbers), which some faster formats can't hold. Only the server writes these files and they're never accepted from users, so loading them is safe. |
| Heavy tasks | **Separate worker process with a time limit** (Python standard library) | Reading, profiling and exporting run in a separate process that is stopped after 60 s, and its memory is capped. A huge file can't freeze or crash the app. No Redis or Celery needed. |
| AI | **Groq (optional)** through plain HTTPS with `httpx` | No vendor SDK. The app works fully without it. |
| PDF reports | **ReportLab** (including its built-in charting) | Free. PDF charts are drawn from the same numbers as the dashboard, so they always match. |
| Testing | **Pytest**, **Vitest**, **Playwright** | Backend logic, frontend logic, and real browser clicks. |
| Packaging | **Docker + Docker Compose** | One command starts everything, the same way on any machine. |
| Security checks | `pip-audit`, `npm audit` | Free scans for known vulnerable libraries. |

What we deliberately **don't** use: Redis, Celery, Postgres, cloud storage, paid APIs, auth providers, analytics trackers.

## 2. System architecture

```
 Browser (Next.js app)
   │  same-origin requests to /api/*  (Next.js forwards them to FastAPI; no CORS exposure)
   ▼
 FastAPI (single service)
   ├── middleware: workspace cookie · rate limiter · request-size guard · error envelope
   ├── routers: health · uploads · sessions · profile · cleaning · dashboard · analyst · exports · settings
   ├── services (pure business logic, no web code):
   │     ingest/      file validation, sheet discovery, CSV/Excel readers
   │     profiling/   type inference, stats, issues Q01–Q16, health score
   │     cleaning/    17 operations, preview, replay engine
   │     analytics/   one query engine for dashboard + AI + exports
   │     analyst/     intent parser (local) · Groq client · explanation verifier
   │     reports/     xlsx + pdf builders
   │     storage/     safe paths, snapshots, retention cleanup
   ├── worker: run_with_limits(task, timeout=60s, memory cap) in a separate process
   └── SQLite (metadata) + ./storage/ (files)
```

**The rule that keeps numbers trustworthy:** the dashboard, the AI Analyst and the exports all call the **same** `analytics.query()` function. No figure is calculated in more than one place.

## 3. Repository structure

```
datadoctor/
├── SPEC.md  PLAN.md  CLAUDE.md  README.md
├── .env.example  docker-compose.yml
├── backend/
│   ├── pyproject.toml / requirements*.txt
│   ├── alembic.ini  migrations/
│   ├── app/
│   │   ├── main.py  config.py  db.py  models.py  errors.py
│   │   ├── middleware/   workspace.py  ratelimit.py
│   │   ├── routers/      health.py uploads.py sessions.py profile.py cleaning.py
│   │   │                 dashboard.py analyst.py exports.py settings.py
│   │   ├── schemas/      Pydantic request/response models
│   │   ├── services/     ingest/ profiling/ cleaning/ analytics/ analyst/ reports/ storage/
│   │   └── worker.py
│   └── tests/            unit/ api/ security/ fixtures/
├── frontend/
│   ├── package.json  next.config.ts  vitest.config.ts  playwright.config.ts
│   ├── src/app/          (marketing)/page.tsx  workspace/  upload/  s/[sessionId]/{health,clean,dashboard,analyst,export}/  settings/
│   ├── src/components/   ui/ (shadcn)  layout/  upload/  health/  cleaning/  dashboard/  analyst/  export/
│   ├── src/lib/          api client, types, formatters, chart-config rules
│   └── tests/            unit/ (vitest)  e2e/ (playwright)
└── sample-data/
    ├── generate.py  README.md (planted issues per file)
    └── retail_sales.xlsx  hr_attendance.csv  transactions_pkr.xlsx  insurance_claims.csv  hospital_utilisation.xls
```

## 4. API contract (v1)

All responses are JSON unless they are file downloads. Errors use the shape `{"error": {"code": "FILE_TOO_LARGE", "message": "...", "id": "err_…"}}`. Every `{session_id}` route checks that the session belongs to the caller's workspace. If it doesn't, the API returns 404 so it doesn't even reveal that the session exists.

| Method & path | Purpose | Notes |
|---|---|---|
| `GET /api/health` | Liveness, version, AI configured? limits | No data |
| `GET /api/settings` · `PUT /api/settings` | Workspace preferences (time zone, date display, AI column-name sharing) | |
| `DELETE /api/workspace/data` | Delete everything for this workspace | Confirmation in UI |
| `POST /api/uploads` | Multipart upload → `{dataset_id, sheets:[{index,name,visibility,rows,cols,formula_cells_without_cache}], file_size, file_type}` | Streamed, size-limited, rate-limited |
| `POST /api/datasets/{id}/sessions` | `{sheet_index, header_row}` → creates session, parses sheet (worker) → session summary | |
| `GET /api/sessions` | Workspace session list | |
| `GET /api/sessions/{sid}` | Summary: columns, types, row count, expiry, operations count | |
| `DELETE /api/sessions/{sid}` | Delete session (and dataset if last) | |
| `GET /api/sessions/{sid}/rows?view=current\|original&offset&limit&columns` | Paged rows (limit ≤ 500) | |
| `GET /api/sessions/{sid}/profile` | Profile + health score + issues (cached by version hash) | Worker for large data |
| `PUT /api/sessions/{sid}/sensitive-columns` | Mark/unmark sensitive | |
| `PUT /api/sessions/{sid}/date-rules` | Dataset-level / per-column date interpretation | |
| `GET /api/cleaning/operations` | Operation catalogue with parameter schemas | Drives the UI forms |
| `POST /api/sessions/{sid}/cleaning/preview` | `{operation_type, parameters}` → `{affected_rows, destructive, before[], after[], warnings[]}` | Doesn't change anything |
| `POST /api/sessions/{sid}/cleaning/apply` | Same body + `confirm: true` for destructive ops → new state | Records an audit entry |
| `POST /api/sessions/{sid}/cleaning/undo` | Undo last active operation | |
| `POST /api/sessions/{sid}/cleaning/reset` | Reset to original | |
| `GET /api/sessions/{sid}/history` | Operations + audit events, in order | |
| `POST /api/sessions/{sid}/query` | Widget spec → aggregated series. `{chart, x, y, agg, group_by, date_grain, filters, sort, limit}` | One engine for everything |
| `GET /api/sessions/{sid}/dashboard` · `PUT …/dashboard` | Load/save layout + widget configs | |
| `GET /api/sessions/{sid}/dashboard/recommendations` | Rule-based initial widgets | |
| `GET /api/sessions/{sid}/analyst/suggestions` | Suggested questions from column types | |
| `POST /api/sessions/{sid}/analyst/ask` | `{question}` or `{operation, params}` → `{interpretation, result, explanation:{source, text, status}}` | Rate-limited |
| `POST /api/sessions/{sid}/exports` | `{type: xlsx\|pdf, options}` → export job | Worker |
| `GET /api/exports/{job_id}` | Job status | |
| `GET /api/exports/{job_id}/download?token=` | File | Short-lived signed token |

The browser receives the OpenAPI schema (`/api/openapi.json`) at build time and turns it into TypeScript types, so the frontend and backend contracts can't drift apart.

## 5. Database schema (as approved in SPEC §8)

Tables: `workspaces`, `datasets`, `worksheets`, `analysis_sessions`, `cleaning_operations`, `audit_events`, `data_profiles`, `dashboard_configurations`, `export_jobs`, `ai_interactions`. Columns are exactly as in SPEC §8. UUIDs are stored as 36-character strings. JSON columns use SQLAlchemy `JSON`. Timestamps are stored in UTC and shown in Asia/Karachi by default. Indexes: `datasets.workspace_id`, `analysis_sessions.dataset_id`, `cleaning_operations(session_id, sequence_number)` unique, `audit_events.session_id`, `export_jobs.session_id`. The first Alembic revision `0001_initial` creates everything. Any change after approval gets a new revision and requires your sign-off.

## 6. Data processing pipeline

```
upload ──► validate (extension + magic bytes + size + zip-bomb + encryption)
       ──► store original as storage/originals/<uuid>.<ext>   (never modified, deleted at expiry)
       ──► discover sheets (workbook XML: names, visibility; formula cells lacking cached <v>)
select sheet + header row ──► worker: read sheet (calamine / pandas-csv) with row/col/cell limits
       ──► normalise headers (blank → "Column N", duplicates → "Name (2)")
       ──► save snapshot storage/snapshots/<session>/v0.pkl      ("original" view)
profile ──► type inference per column ─► stats ─► issues Q01–Q16 ─► health score ─► cache by version hash
clean   ──► preview(op) on current snapshot (read-only) ─► apply: append op, run, save v<n>.pkl
            current = v0 + active ops replayed (cached: keep the last 3 snapshots; older ones rebuilt on demand)
            undo: mark last op undone → load previous snapshot or replay · reset: mark all undone → v0
query   ──► analytics.query(current snapshot, spec) ─► filters ─► group/aggregate ─► cap 500 points
analyst ──► interpret ─► validate ─► analytics/profiling function ─► (optional) Groq explanation ─► verifier
export  ──► worker: same query/profile functions ─► openpyxl / reportlab ─► storage/exports/<uuid>
retention ► hourly + at startup: delete expired originals, snapshots, exports; mark rows expired
```

**Type inference** (deterministic). For each column the app looks at all non-missing values (or a 50,000-value stratified sample when larger, and the sample size is shown). Each value is classified as native number / numeric text / native date / date text (by pattern) / boolean / text. The dominant class sets the column type, and values outside it count as type-inconsistent (feeds T in the health score).

## 7. Screen implementation plan

| Screen | Route | Main components | Data sources |
|---|---|---|---|
| Landing | `/` | Hero, HowItWorks, FeatureGrid, PrivacyNote, "Try sample data" | `POST /uploads` with a bundled sample (badged "Sample data") |
| Workspace | `/workspace` | SessionTable, EmptyState, DeleteDialog | `GET /sessions` |
| Upload Studio | `/upload` | DropZone (XHR progress), ValidationList, SheetPicker, HeaderRowSelect, PreviewGrid | uploads, sessions, rows |
| Data Health Center | `/s/[id]/health` | ScoreGauge, ScoreBreakdown, KpiTiles, MissingChart, DuplicatePanel, ColumnProfileCards, IssueTable | profile |
| Cleaning Studio | `/s/[id]/clean` | VirtualGrid, ToolPalette, OperationForm (generated from schema), PreviewPanel, ConfirmDialog, HistoryTimeline, Undo/Reset, DateInterpretationDialog | cleaning/*, rows, history |
| Dashboard Studio | `/s/[id]/dashboard` | KpiRow, WidgetGrid, WidgetCard, WidgetEditorDrawer, FilterBar, PNG download | dashboard, query, recommendations |
| AI Analyst | `/s/[id]/analyst` | ChatThread, SuggestionChips, GuidedBuilder, AnswerCard (Computed / AI blocks), AiStatusPill | analyst/* |
| Export Center | `/s/[id]/export` | ExportOptions, ReportOutline, ExportJobList | exports |
| Settings | `/settings` | ThemeToggle, TimezoneSelect, DateDisplay, AiStatus, PrivacySwitches, Limits, DeleteAll | settings, health |

Shared across screens: AppShell (sidebar + mobile drawer + "Local mode" badge), Toaster, skeleton loaders, error boundary with retry, and a session switcher in the header.

## 8. Milestones and tasks (each task ≤ 60 min)

Each milestone ends with: run the app → run the tests → fix → update CLAUDE.md → commit and push → demo notes → **"Keep going?"**

| M | Milestone | Tasks | Tests that prove it |
|---|---|---|---|
| **1** | Repo setup, architecture, dev environment | 1.1 Folder skeleton, `.gitignore`, `.env.example` · 1.2 Backend venv, pinned requirements, `pip-audit` · 1.3 Frontend Next.js + Tailwind v4 + shadcn init + Inter, `npm audit` · 1.4 Make-style scripts (`dev`, `test`, `lint`) documented in CLAUDE.md | Backend and frontend both start. Lint/typecheck pass. Audits clean. |
| **2** | Frontend shell, branding, navigation | 2.1 Theme tokens (palette, light/dark, contrast check) · 2.2 AppShell: sidebar, mobile drawer, header, Local-mode badge · 2.3 Landing page (no fake numbers) · 2.4 Route placeholders that show honest "available in milestone N" states, not fake controls | Vitest: theme/contrast util. Playwright: navigation at 360/768/1280 px, screenshots. |
| **3** | Backend, database, health checks | 3.1 FastAPI app, config, error envelope · 3.2 SQLAlchemy models + Alembic `0001_initial` · 3.3 Workspace cookie middleware + ownership helper · 3.4 Rate limiter · 3.5 `/api/health`, settings endpoints, frontend proxy wiring | Pytest: migrations from scratch, health, cookie issuance, 404 on another workspace's id, rate-limit 429. |
| **4** | File upload, validation, worksheet selection | 4.1 Streamed upload + size limit + safe storage · 4.2 Magic-byte checks, zip-bomb guard, encryption detection · 4.3 Sheet discovery (names, visibility, formula cache scan) · 4.4 CSV encoding/delimiter detection · 4.5 Upload Studio UI with real progress + SheetPicker | Pytest: valid xlsx/xls/csv, multi-sheet, hidden sheet, empty, corrupted, wrong extension, encrypted, UTF-16/1252, oversize, malicious file names. Playwright: upload flow. |
| **5** | Spreadsheet preview and profiling | 5.1 Worker with timeout and memory cap · 5.2 Sheet parsing + header normalisation + limits · 5.3 Paged rows endpoint + VirtualGrid · 5.4 Type inference · 5.5 Column statistics (numeric, date, category) | Pytest: preview equals source cells. Type inference on mixed columns. Worker timeout kills a slow task. Benchmark script run on 200k × 50 with results recorded. |
| **6** | Data health score and issue detection | 6.1 Issues Q01–Q08 · 6.2 Issues Q09–Q16 incl. CNIC/phone/email detection · 6.3 Health score formula + breakdown · 6.4 Data Health Center UI | Pytest: each issue on a crafted dataset with exact counts. Health score hand-calculated case. Playwright: health page renders the score breakdown. |
| **7** | Cleaning engine and transformation preview | 7.1 Operation framework (schema, preview, apply, destructive flag) · 7.2 Ops 1–6 (duplicates, whitespace, case, categories) · 7.3 Ops 7–11 (numbers, dates with interpretation rules, missing values) · 7.4 Ops 12–17 (rows, columns, outliers, type flags) · 7.5 Cleaning Studio UI: palette, forms, preview, confirm | Pytest per operation (expected output, preview count = applied count). Ambiguous dates blocked without a rule. No zero-fill unless chosen. |
| **8** | Cleaning history, undo, reset | 8.1 Replay engine + snapshot cache · 8.2 Undo/reset endpoints + audit events · 8.3 History timeline + before/after comparison UI | Pytest: random op sequences → reset equals original byte-for-byte (via DataFrame equality). Undo restores the previous state. Audit order. Playwright: apply → undo → reset. |
| **9** | Dashboard calculations and chart configuration | 9.1 `analytics.query` (aggregations, grouping, date grain, filters, sort, limit) · 9.2 Compatibility rules (which agg works with which type) shared with the frontend · 9.3 Recommendations engine · 9.4 Dashboard config persistence | Pytest: every aggregation vs an independent pandas calculation. Date filtering edges. Distinct counts. Empty results. Invalid configs → 422. Vitest: compatibility rules. |
| **10** | Interactive Dashboard Studio | 10.1 Widget components for 8 chart types · 10.2 Widget editor drawer · 10.3 Filter bar + date range · 10.4 Grid layout (reorder, width) + PNG download · 10.5 Empty states | Playwright: build a chart, change agg, filter, reorder, reload persists. Values shown equal the API values. |
| **11** | AI Analyst with deterministic local operations | 11.1 14 allowlisted operations wired to analytics/profiling · 11.2 Local rule-based interpreter · 11.3 Guided question builder · 11.4 Analyst UI (chat, suggestions, answer cards) | Pytest: example questions → expected operation and params. Unsupported questions → honest message. Invalid column → error. Playwright: ask with no AI key. |
| **12** | Optional Groq integration | 12.1 Groq client (timeout, errors) · 12.2 Intent-to-operation JSON with schema validation · 12.3 Explanation generation + verifier (numbers, dates, labels) · 12.4 Privacy filter (aliases, sensitive columns) + AI status in Settings | Pytest with a mocked provider: valid mapping, invalid JSON, timeout, missing key, fabricated number rejected, sensitive column never in payload. A live check only if you supply a key (reported separately). |
| **13** | Excel and PDF exports | 13.1 Export job + worker + signed download · 13.2 Excel (4 sheets, formatting, formula-injection escape) · 13.3 PDF (sections, charts via ReportLab, time zone) · 13.4 Export Center UI | Pytest: reopen xlsx and compare totals with the query engine. Escaped cells. PDF contains section headings (text extraction). Token expiry. |
| **14** | Security, edge cases, regression | 14.1 Security test suite (traversal, cross-workspace, oversize, filenames, injection, CORS) · 14.2 Edge-case suite from SPEC §14 · 14.3 Five synthetic datasets + planted-issue README · 14.4 Fix findings + regression tests | All suites green. Audits clean. |
| **15** | UI polish, responsive, accessibility | 15.1 Loading/empty/error states pass · 15.2 Keyboard navigation + focus + aria · 15.3 Contrast check on both themes · 15.4 Mobile layouts | Playwright: axe-core accessibility scan, screenshots at 3 widths. Keyboard-only walkthrough. |
| **16** | Docker, README, deployment preparation | 16.1 Backend/frontend Dockerfiles (non-root, slim) · 16.2 docker-compose with volumes + healthchecks · 16.3 README, setup, deployment guide, security checklist, limitations, roadmap · 16.4 Clean-checkout verification | `docker compose up` from a fresh clone. Full e2e run against the containers. |

## 9. Testing strategy

- **Backend (Pytest):** unit tests per service function, API tests through FastAPI's test client, and a security suite. Fixtures are generated in code (no hand-edited binaries), with a few small committed files for format checks (`.xls`, an encrypted `.xlsx`).
- **Correctness oracle:** every analytics result is compared with a second, independently written Pandas expression in the test.
- **Frontend (Vitest):** formatters (PKR, DD/MM/YYYY, Asia/Karachi), chart-config compatibility rules, API error handling.
- **End-to-end (Playwright, pre-installed Chromium):** upload → health → clean → undo/reset → dashboard → analyst → export, at 360/768/1280 px, plus an axe accessibility scan.
- **Performance:** `backend/scripts/benchmark.py` generates a 200k × 50 file and records parse/profile/preview/query timings in README. These are real numbers from the actual machine, and the machine is stated alongside them.
- **Reporting rule:** test counts and outcomes are copied from actual runs. Anything not run is listed as "not verified".

## 10. Security checkpoints

| When | Checkpoint |
|---|---|
| M3 | Ownership checks on every route (test fails if a new route skips it). No stack traces in responses. Cookie flags. |
| M4 | Upload validation, safe file names, path-containment helper, zip-bomb guard, encryption handling |
| M5 | Worker isolation: time and memory limits |
| M12 | AI payload privacy filter; key never reaches the browser; prompt-injection text is treated as data |
| M13 | Formula-injection escaping, signed short-lived download tokens, export expiry |
| M14 | Full security suite, `pip-audit`, `npm audit`, review of logs for data leakage |
| M16 | Containers run as non-root, `.env` excluded, CORS from config, a "public deployment is blocked without auth" check in README |

## 11. Deployment requirements

- **Local (MVP target):** Docker Desktop or Docker Engine 24+, about 2 GB free RAM, `docker compose up` → http://localhost:3000.
- **Without Docker:** Python 3.12+, Node 20+. Commands are documented in CLAUDE.md and README.
- **Configuration:** `.env` (copied from `.env.example`): `MAX_UPLOAD_MB`, `RETENTION_DAYS`, `PROCESS_TIMEOUT_S`, `WORKER_MEMORY_MB`, `MAX_ROWS`, `MAX_COLUMNS`, `MAX_CELLS`, `DISPLAY_TIMEZONE`, `GROQ_API_KEY` (optional), `GROQ_MODEL`, `CORS_ORIGINS`, `SECRET_KEY` (signs download tokens and cookies).
- **Public hosting:** not part of the MVP. It would need authentication (a future milestone), HTTPS, and a server around 2 vCPU / 4 GB, which costs about US$5–10/month (needs your approval).

## 12. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Large or wide workbooks exhaust memory | Crash, slow app | Row/column/cell limits, worker memory cap, calamine reader, paged views, benchmark published |
| Wrong date interpretation | Wrong analysis | Never guess; evidence-based prompt; conflicts reported as failures; regression tests |
| AI states made-up figures | Loss of trust | AI never calculates; verifier rejects unknown numbers/dates/labels; computed and explained blocks shown separately |
| Personal data sent to AI | Privacy breach | Metadata/aggregates only, sensitive-column detection, column aliasing switch, tests on payloads |
| Undo/replay drift | Data not recoverable | Original never modified; deterministic ops; property-style tests (random sequences → reset equals original) |
| Formula injection in exports | Harm to the person opening the file | Escaping plus tests |
| Calamine edge cases (rare formats) | File not readable | Fall back to OpenPyXL for xlsx, and report a clear error |
| Local-mode app exposed on the internet | Data exposure | Bind to localhost by default in compose; README warning; banner in the UI |
| Scope growth | Delays | Excluded list in SPEC §16; changes need your approval |
| Free-tier AI limits | AI unavailable | Local fallback is always available, with a clear message |

## 13. Definition of done

As in SPEC §17. In addition, every milestone in section 8 is committed with its tests passing, CLAUDE.md reflects the final state, and the README's test-results and benchmark sections contain output from real runs.
