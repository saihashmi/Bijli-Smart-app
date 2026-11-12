# DataDoctor AI — Product Specification (SPEC.md)

> **From Messy Data to Meaningful Decisions.**

| | |
|---|---|
| Status | **Draft v1.0, awaiting product-owner approval** |
| Phase | 01 SPEC (no application code is written until this document is approved) |
| Location | `datadoctor/` in this repository, kept separate from the earlier Bijli Smart code |
| Date | 2026-11-12 |

### Assumed defaults (from the clarification round)

The product owner asked to proceed, so these defaults apply. You can change any of them before approval.

| # | Topic | Default adopted |
|---|---|---|
| D1 | Deployment | Runs locally with Docker Compose. A later public deployment needs separate approval and authentication first (see D2). |
| D2 | Authentication | **Local-only mode**: one user on their own machine, labelled "Local mode, not for public hosting" everywhere in the app. A server-issued workspace cookie keeps datasets separate between browsers, but it is **not** treated as authentication. |
| D3 | Retention and privacy | Uploaded originals and working copies are deleted automatically after **7 days** (configurable). Users can delete any dataset immediately. Data never leaves the server unless the user opts in. Raw cell values are never logged. |
| D4 | Workload | Maximum file size **20 MB** (configurable). One active dataset per analysis session. 1–3 people using it at once. Each processing step is limited to **60 s**. Benchmark target: 200,000 rows × 50 columns, with real results reported. `.xls` is supported read-only. |
| D5 | AI | **Optional Groq**, free tier, model `llama-3.3-70b-versatile`. Off unless `GROQ_API_KEY` is set. Groq receives only metadata and results the app has already calculated. A Settings switch can also hide column names from the AI. |

---

## 1. Product overview

DataDoctor AI is a self-service web application. Users upload Excel or CSV files, see an explained list of data-quality problems, fix them with safe, reversible cleaning operations, build dashboards from the real data, ask analytical questions in plain English, and export a cleaned workbook and a PDF report. No code is needed at any step.

**Core experience:** Upload → Profile → Clean → Analyze → Visualize → Export

**Guiding principles**

1. **Numbers are computed, never generated.** Pandas/NumPy functions on the server calculate every figure. The AI only interprets user intent and explains results that are already verified.
2. **The original file is never changed.** Cleaning works on a copy. Every operation is logged, previewed, reversible and reproducible.
3. **No pretend features.** Every button does something real. Nothing shown is fake data or a placeholder metric. Sample datasets are always labelled as samples.
4. **Privacy by default.** Files stay on the server, and AI calls carry only metadata and aggregates.
5. **Pakistan first.** PKR examples, Asia/Karachi time zone, support for DD/MM/YYYY dates, and awareness of CNIC numbers as personal identifiers.

## 2. User personas

| Persona | Context | Goal | Pain today |
|---|---|---|---|
| **Ayesha, Excel analyst** (retail chain, Lahore) | Weekly sales exports from three branches' POS systems | One clean sales table and a monthly dashboard for management | Mixed date formats, "Lahore " vs "lahore", amounts stored as text with "Rs" |
| **Bilal, SME owner** (distribution business, Karachi) | Keeps invoices and expenses in Excel | Know which products and months make money | No advanced Excel skills, no analyst on staff |
| **Sana, insurance/health claims analyst** | Claims and utilisation extracts that contain identifiers | Quality-check a file before reporting and summarise claim trends | Must not leak patient or member identifiers. Duplicate claims inflate totals. |
| **Usman, HR officer** | Attendance and leave sheets | Absenteeism by department and month | Blank cells, duplicate employee-day rows, inconsistent department names |
| **Hira, freelancer/consultant** | Gets messy client files | Return a cleaned workbook and a professional PDF quickly | Manual cleaning is slow and hard to explain to clients |

## 3. Core user stories

| ID | As a… | I want to… | So that… |
|---|---|---|---|
| US-01 | user | drag a .xlsx, .xls or .csv file into the app and see upload progress | I know it is being received |
| US-02 | user | choose which worksheet to analyse, including hidden ones (clearly labelled) | I work on the right table |
| US-03 | user | preview the first rows and see the row count, column count, file size and detected types | I can confirm the file was read correctly |
| US-04 | user | see a Data Health Score and how it was calculated | I understand overall quality at a glance |
| US-05 | user | see each issue with its column, affected-row count, severity, examples and a suggested fix | I know exactly what is wrong and what to do |
| US-06 | user | preview a cleaning operation's before/after effect and affected-row count before applying it | nothing happens that I did not expect |
| US-07 | user | be asked what ambiguous dates like 03/04/2026 mean | my dates are never silently wrong |
| US-08 | user | undo the last operation, or reset to the original | I can experiment safely |
| US-09 | user | see a full history of operations applied | my work is auditable and repeatable |
| US-10 | user | get an initial dashboard automatically, then change its charts, axes, aggregations, filters and titles | I get insight quickly and can tailor it |
| US-11 | user | ask "Which month has the highest sales?" and get a verified answer | I don't need formulas |
| US-12 | user | see which parts of an answer are computed facts and which are AI explanation | I know what to trust |
| US-13 | user | use everything except AI explanations without an AI key | the app is useful offline and for free |
| US-14 | user | download a cleaned Excel workbook with quality report, audit log and statistics | I can share and continue in Excel |
| US-15 | user | download a PDF report with charts and findings | I can present the results |
| US-16 | user | delete my dataset at any time and know when it will expire | my data is under my control |
| US-17 | user | mark columns as sensitive | they are never sent to the AI or shown in AI-bound results |

## 4. Functional requirements

### FR-1 Upload and ingestion
- FR-1.1 Drag-and-drop and a file browser, with a real upload progress bar driven by actual bytes sent.
- FR-1.2 Accept `.xlsx`, `.xlsm` (macros are ignored and never run), `.xls` and `.csv`. Reject everything else with a clear message.
- FR-1.3 Check the file's actual content as well as its extension: the ZIP signature for xlsx, the OLE signature for xls, and decodable text for CSV.
- FR-1.4 Enforce a configurable size limit (default 20 MB) on the server while streaming the upload, plus a limit on the uncompressed size of xlsx files to block "zip bombs".
- FR-1.5 List all worksheets with row and column counts and visibility (visible / hidden / very hidden). The user picks one, and the first visible sheet is pre-selected.
- FR-1.6 Show a preview of the first 100 rows (paged), the row and column count, the file size, column names and detected types.
- FR-1.7 Detect the CSV encoding (UTF-8, UTF-8 with BOM, UTF-16, Windows-1252/Latin-1) and delimiter (`,` `;` tab `|`). Report when bytes could not be decoded instead of dropping them silently.
- FR-1.8 Rename blank and duplicate headers deterministically (`Column 3`, `Amount (2)`) and report it as an issue.
- FR-1.9 Detect password-protected or encrypted workbooks and explain that they are not supported (remove the password in Excel first).
- FR-1.10 Never evaluate formulas. Use cached values only, and report how many formula cells have no cached value ("formula result not saved; open and save the file in Excel to fix").
- FR-1.11 Header row detection: row 1 by default, and the user can choose a different header row (0–20) if the sheet has title rows.
- FR-1.12 One active dataset per analysis session. Uploading a new file starts a new session and keeps older sessions listed in the Workspace until they expire.

### FR-2 Profiling
- FR-2.1 Dataset level: rows, columns, missing cells (and %), exact duplicate rows, completely empty rows and columns.
- FR-2.2 Column level: detected type (number, integer, text, category, date, date-time, boolean, mixed), non-missing count, missing count and %, unique count, top 10 values with frequencies, and examples.
- FR-2.3 Numbers: min, max, mean, median, standard deviation, quartiles, histogram bins, negative and zero counts, and the count of numbers stored as text.
- FR-2.4 Dates: min, max, the formats detected and their counts, how many values are ambiguous, invalid or in the future, and Excel serial candidates.
- FR-2.5 The Data Health Score (section 10.2) with a breakdown of its components and its limitations.
- FR-2.6 An issue list (section 10.1). Each issue shows: type, column, affected rows, severity, up to 5 example values with their row numbers, and a suggested action that links to the matching cleaning operation.
- FR-2.7 Profiles are cached per dataset version and recalculated after every cleaning change.

### FR-3 Cleaning
- FR-3.1 Supports the 17 operations defined in section 11.
- FR-3.2 Every operation has a **preview** first: affected-row count plus before/after sample rows, calculated on the full data. Nothing changes until the user clicks Apply.
- FR-3.3 Destructive operations (anything that removes rows or columns, or overwrites values) need a confirmation dialog that states the count.
- FR-3.4 Operations are stored as an ordered list with their parameters. The current data is always the original data with that list replayed, so results are reproducible.
- FR-3.5 **Undo** removes the most recent active operation. **Reset** clears all operations. Both are recorded in the audit trail and nothing is erased from history.
- FR-3.6 Before/after comparison shows the selected columns, original vs current, for a page of rows.
- FR-3.7 Conversion failures (dates or numbers that could not be converted) are never silently blanked. The raw value is kept in a companion column (`<col>__raw`) or listed in the failure report, whichever the user chooses (default: failure report plus the value set to missing in the converted column, with a count).

### FR-4 Dashboard Studio
- FR-4.1 Chart types: KPI card, bar, line, pie, donut, histogram, scatter and data table.
- FR-4.2 Automatic initial dashboard of up to 6 widgets built from column types only (section 12.4). Recommendations explain why each was chosen.
- FR-4.3 Per-widget configuration: chart type, X field, Y field, aggregation, group-by (series), date grain (day/week/month/quarter/year), sort (by value or label, ascending or descending), top-N limit, title.
- FR-4.4 Aggregations: count, sum, average, min, max, median and distinct count. Only valid combinations can be selected (for example, no sum on text).
- FR-4.5 Dashboard filters: category include/exclude, numeric range, and a date range. They apply to all widgets and KPI cards.
- FR-4.6 The server does all aggregation. The browser only receives aggregated series, capped at 500 points per chart (anything beyond that is grouped as "Other" or the user is told to filter).
- FR-4.7 Layout: responsive grid. Widgets can be reordered and resized between half and full width. Layout is saved per session.
- FR-4.8 Clear empty states with reasons (for example "No date column: a line chart over time needs a date").
- FR-4.9 The current dashboard can be exported as a PDF (FR-6) and each chart as a PNG.

### FR-5 AI Analyst
- FR-5.1 A chat-style panel with suggested questions generated from the dataset's column types.
- FR-5.2 Questions are mapped to the **allowlisted operations** in section 12.2. Parameters are validated against the real columns, and results are calculated locally.
- FR-5.3 **Without an AI key:** a built-in rule-based interpreter handles common phrasings, and a guided question builder (operation + column dropdowns) covers everything else. All operations work.
- FR-5.4 **With an AI key:** Groq turns the question into an operation request (JSON matching a fixed schema) and, optionally, writes a short explanation of the computed result.
- FR-5.5 Every answer shows **Computed result** (table, number or chart from the server) separately from **AI explanation** (labelled with the provider and model).
- FR-5.6 AI explanations are checked: any number, date or label not present in the computed result is rejected, and the explanation is replaced by the local template explanation, with a note.
- FR-5.7 Unsupported or unanswerable questions get an honest "I can't answer that with this data or the supported operations", plus the nearest supported alternatives.
- FR-5.8 AI explains issues and suggests cleaning operations only from the issue list. It cannot invent issues or operations.
- FR-5.9 Each interaction is stored as question, operation, parameters and a result summary.

### FR-6 Exports
- FR-6.1 **Excel workbook**: (1) Cleaned Data, (2) Data Quality Report, (3) Cleaning Audit Log, (4) Summary Statistics. Header styling, frozen panes, auto-filter and column widths are applied.
- FR-6.2 **PDF report**: title, dataset summary, health score with breakdown, key statistics, data-quality findings, cleaning summary, selected dashboard charts, and AI insights (only those that passed verification, clearly labelled).
- FR-6.3 Every export carries its generation timestamp with the time zone (default Asia/Karachi, set in Settings).
- FR-6.4 Exported figures come from the same calculation functions as the dashboard, so they always match.
- FR-6.5 Formula-injection protection: any text cell starting with `=`, `+`, `-`, `@`, tab or carriage return gets a leading apostrophe-equivalent (stored as a plain string with `'` prefix).
- FR-6.6 Exports can be downloaded only by the session's workspace, through a short-lived download link. Export files are deleted after 24 hours or when the dataset expires.

### FR-7 Workspace and Settings
- FR-7.1 Workspace lists sessions: file name, sheet, rows, health score, last activity, expiry date, and buttons to open and delete.
- FR-7.2 Settings shows: theme (light/dark/system), display time zone, date display preference (DD/MM/YYYY default), AI provider status (configured / not configured / last error), an "allow sending column names to AI" switch (default on), sensitive-column handling, retention period (read-only, from server config), file limits (read-only), and a "Delete all my data" button.

## 5. Non-functional requirements

| ID | Area | Requirement |
|---|---|---|
| NFR-1 | Correctness | Calculations are verified against independent Pandas calculations in tests. Totals in exports equal totals on screen. |
| NFR-2 | Performance | A 20 MB CSV / 200k × 50 benchmark: profile in ≤ 30 s, a cleaning preview in ≤ 5 s, dashboard widget queries in ≤ 2 s on a 2-vCPU / 4 GB machine. The real benchmark numbers will be published. They are not guaranteed for every 20 MB file (wide sheets and long text use more memory). |
| NFR-3 | Responsiveness | Long jobs (parsing, profiling, export) run in the background with progress or status updates. The UI never freezes. Tables are paged and virtualised. |
| NFR-4 | Resource limits | Configurable: max file size, max uncompressed xlsx size, max rows (default 1,000,000), max columns (default 500), max cells (default 20 million), and a 60 s timeout per step. Exceeding a limit gives a specific message. |
| NFR-5 | Availability | Works fully offline except for optional AI. |
| NFR-6 | Cost | Free open-source stack. Runs on one small machine. No paid services. |
| NFR-7 | Accessibility | WCAG 2.1 AA contrast, full keyboard operation, visible focus, labelled form controls, charts with text or table alternatives. |
| NFR-8 | Responsive UI | Works from 360 px (phone) to wide desktop. Sidebar on desktop, drawer or bottom navigation on mobile. |
| NFR-9 | Maintainability | Business logic is separate from UI. Typed API contracts. Automated tests for the backend (Pytest), frontend logic (Vitest) and end-to-end flows (Playwright). |
| NFR-10 | Observability | Structured logs that contain no cell values. A job history with durations and error codes. |
| NFR-11 | Localisation | English UI for the MVP. PKR currency formatting (`Rs 1,234,567` / `PKR`). Asia/Karachi time zone. |

## 6. Screen specifications

All screens use the brand palette: navy `#0F172A`, electric blue `#2563EB`, teal `#14B8A6`, background `#F8FAFC`, success `#16A34A`, warning `#F59E0B`, error `#DC2626`. Light and dark themes. The Inter font is self-hosted so it loads with no external request. Desktop has a left sidebar (Workspace, Upload, Health, Cleaning, Dashboard, AI Analyst, Export, Settings), and mobile has a top bar with a navigation drawer. A persistent "Local mode" badge appears when D2 applies.

| # | Screen | Key contents | Primary actions | States |
|---|---|---|---|---|
| 01 | **Landing** | Hero with tagline, the "Upload → Profile → Clean → Analyze → Visualize → Export" explainer, feature cards, privacy statement, and a **genuine demo**: a button that loads a synthetic sample dataset, clearly badged "Sample data" | Upload a file; Try with sample data | — |
| 02 | **Workspace** | Sessions table (file, sheet, rows, health score, last activity, expires), empty state | Open, delete (with confirmation), new upload | Loading skeleton, empty, error |
| 03 | **Upload Studio** | Drop zone, progress bar, validation results, worksheet picker (visibility badges, dimensions), header-row selector, paged preview, column list with detected types | Upload, choose sheet, confirm and profile | Uploading %, validating, rejected (reason), password-protected, empty sheet |
| 04 | **Data Health Center** | Score gauge with component bars and formula, KPI tiles (rows, columns, missing %, duplicates), missing-values chart by column, duplicates panel, column profile cards (type, stats, histogram or top values), issue list filterable by severity or column | Go to fix (opens Cleaning Studio with the operation prefilled), mark column sensitive | Profiling progress, no issues found |
| 05 | **Cleaning Studio** | Paged spreadsheet grid (virtualised), tool palette grouped as Rows / Text / Types & Dates / Missing / Columns / Detection, operation form, preview panel (affected rows plus before/after), history timeline | Preview, Apply (confirmation if destructive), Undo, Reset to original, before/after toggle | Preview computing, nothing to change (0 rows affected), conflict (for example ambiguous dates unresolved) |
| 06 | **Dashboard Studio** | KPI row, widget grid, filter bar (date range, categories, numeric ranges), widget editor drawer | Add widget, edit, duplicate, delete, reorder, reset to recommended, export PDF, download PNG | Empty-state reasons per widget, loading per widget |
| 07 | **AI Analyst** | Chat thread, suggested-question chips, guided question builder, answer cards with a **Computed result** block and a separate **AI explanation** block, "add to dashboard" for chart answers, AI status pill | Ask, build question, add chart to dashboard | AI off (local interpreter), AI error with fallback, unsupported question |
| 08 | **Export Center** | Excel and PDF options (sheets/sections to include, charts to include, include AI insights yes/no), report preview (rendered first page image or section outline), recent exports with expiry | Generate Excel, generate PDF, download | Generating progress, ready, failed (reason) |
| 09 | **Settings** | Theme, time zone, date display, AI status and privacy switches, sensitive columns, retention and limits (read-only), delete all data | Save, delete all (confirmation) | Saved notice |

## 7. User journeys

**J1. First-time analyst (happy path):** Landing → Upload `sales.xlsx` → sees 3 worksheets, chooses "Sales 2025" → preview looks right → Profile → Health 68/100 "Needs attention", 7 issues → clicks "Fix" on *Inconsistent category labels (City)* → preview shows "lahore", "Lahore " and "LAHORE" become "Lahore" across 412 rows → Apply → Dates issue: 03/04/2026-style values are ambiguous → app asks DD/MM or MM/DD and shows evidence (for example 37 values like 25/03/2026 are only valid as DD/MM) → user confirms DD/MM → Health recalculates to 91 → Dashboard shows a recommended monthly sales line, top cities bar, and an amount KPI → AI Analyst: "Which month has the highest sales?" → computed answer: *2025-12, Rs 4,812,300 (sum of Amount)*, with the AI explanation below it → Export: Excel + PDF.

**J2. No AI key:** Same as J1. The AI Analyst shows "AI explanations are off. Answers are computed locally." The rule-based interpreter answers the same question. For unrecognised phrasing, the guided builder is offered.

**J3. Mistake and recovery:** User removes column "Notes" → realises it was needed → Undo → column returns, and the audit log shows both "Remove columns" and "Undo". Later the user clicks **Reset to original** (confirmation) → the data equals the upload exactly.

**J4. Sensitive claims file:** Upload `claims.csv` → the app flags `CNIC` and `Member Name` as likely personal identifiers and suggests marking them sensitive → user accepts → the AI never receives those column names or their values, and group-by results on them are never sent to the AI.

**J5. Bad files:** Password-protected xlsx → "This workbook is password-protected. Remove the password in Excel and upload again." Empty CSV → "The file has no data rows." `.docx` renamed to `.xlsx` → "The file content is not a valid Excel workbook."

## 8. Data model

UUID primary keys. SQLite holds **metadata only**. Dataset contents live as files in controlled local storage (original file plus working snapshots in columnar format) under generated names. Alembic manages migrations.

The entities you suggested are kept. Additions are marked **(+)** and need your approval as part of this spec.

```
WORKSPACE (+)              # local-mode ownership scope (server-issued cookie), not authentication
  id, created_at, last_seen_at, settings_json

DATASET
  id, workspace_id (+), original_filename (sanitised, display only), file_type, file_size,
  sha256 (+), storage_reference (generated name), uploaded_at, expires_at,
  status (uploaded | parsed | failed | deleted)

WORKSHEET
  id, dataset_id, sheet_name, sheet_index (+), visibility (+ visible|hidden|very_hidden),
  row_count, column_count, formula_cells_without_cache (+)

ANALYSIS_SESSION
  id, dataset_id, worksheet_id, header_row (+), date_rules_json (+), sensitive_columns_json (+),
  created_at, updated_at, status (active | archived | expired)

CLEANING_OPERATION
  id, session_id, sequence_number, operation_type, parameters_json, affected_rows,
  status (+ active | undone), created_at, undone_at (+)

AUDIT_EVENT (+)            # reset, undo, export, delete, AI-opt-in changes
  id, session_id, event_type, details_json, created_at

DATA_PROFILE
  id, session_id, version_hash (+ hash of active operation list), profile_json, calculated_at

DASHBOARD_CONFIGURATION
  id, session_id, configuration_json, updated_at

EXPORT_JOB
  id, session_id, export_type (xlsx | pdf), status, storage_reference (+), options_json (+),
  created_at, completed_at, expires_at (+), error (+)

AI_INTERACTION
  id, session_id, question, operation_type, parameters_json (+), result_summary,
  provider (+ local | groq), explanation_status (+ none | verified | rejected), created_at
```

**Undo model:** current data = original sheet + active operations replayed in order. Snapshots are cached after each operation so undo doesn't need a full replay. Undo marks the last active operation `undone`, so history is never deleted.

**Retention:** a cleanup task runs at startup and every hour. It deletes the files and marks the rows `expired` for datasets past `expires_at`. Deleting a dataset removes all its files at once.

## 9. Supported file formats

| Format | Reader | Notes |
|---|---|---|
| `.xlsx` / `.xlsm` | OpenPyXL, read-only, cached values only | Macros are never run. Formulas are never evaluated. All sheets are listed, including hidden ones. Encrypted workbooks are detected and rejected. |
| `.xls` (Excel 97–2003) | xlrd 2.x, read-only | Date cells use the workbook's 1900/1904 date system. Hidden sheets are detected. Password-protected files are rejected. |
| `.csv` (and `.txt` with delimiters) | Pandas with encoding and delimiter detection | Single table. Encodings: UTF-8, UTF-8 BOM, UTF-16, Windows-1252/Latin-1 fallback, with decode issues reported. |

Not supported in the MVP: `.ods`, `.xlsb`, `.json`, Google Sheets links, database connections, more than one table per sheet, and merging several files.

## 10. Data-quality rules

### 10.1 Issue catalogue

Severity: **High** means results will probably be wrong if it isn't fixed. **Medium** means some results may be wrong. **Low** is cosmetic or worth reviewing.

| Code | Issue | Detection rule (deterministic) | Default severity | Suggested operation |
|---|---|---|---|---|
| Q01 | Exact duplicate rows | Rows equal in every column (after no transformation) | High if > 1% of rows, otherwise Medium | Remove exact duplicates |
| Q02 | Possible key duplicates | Only when the user selects key columns: rows repeating the key with differing other values | Medium (informational; never auto-removed) | Review / remove by key |
| Q03 | Missing values | Null, empty, whitespace-only, or a null token (`NA`, `N/A`, `null`, `none`, `-`, `--`, `#N/A`) | High if > 20% of a column, Medium 5–20%, Low < 5% | Missing-value handling |
| Q04 | Completely empty rows / columns | All cells missing | Low | Remove empty rows / columns |
| Q05 | Leading/trailing whitespace | `value != value.strip()` | Low (Medium if it splits categories) | Trim whitespace |
| Q06 | Repeated internal spaces | Contains two or more consecutive spaces | Low | Normalise spaces |
| Q07 | Inconsistent category labels | In a text column with ≤ 200 distinct values, labels that become equal after trimming, collapsing spaces and case-folding (for example "Lahore", "lahore ", "LAHORE") | Medium | Normalise category labels |
| Q08 | Numbers stored as text | In a column where ≥ 80% of non-missing values parse as numbers after removing `,`, currency markers (`Rs`, `PKR`, `$`), `%` or parentheses | Medium | Convert numeric text |
| Q09 | Mixed types | A column whose dominant type covers < 95% of non-missing values | Medium | Flag inconsistent types / convert |
| Q10 | Multiple date formats | A date-like column with more than one detected format pattern | Medium | Normalise dates |
| Q11 | Ambiguous dates | Values where both day/month readings are valid (both parts ≤ 12) and no dataset rule has been set yet | High (blocks date normalisation until resolved) | Ask user for date interpretation |
| Q12 | Invalid dates | A date-like column with values that fail every accepted format, or impossible dates (31/02/2026) | Medium | Report conversion failures |
| Q13 | Possible outliers | Numeric values outside Q1 − 3×IQR … Q3 + 3×IQR (needs ≥ 20 values and IQR > 0) | Low (informational) | Flag outliers (never auto-delete) |
| Q14 | Duplicate / blank headers | Renamed during ingestion | Low | Rename columns |
| Q15 | Formula cells without cached values | Found while reading the workbook | Medium | Informational (fix in Excel) |
| Q16 | Possible personal identifiers | Column name matches (cnic, nic, passport, phone, mobile, email, name, mrn, patient, member id, address, dob) **or** values match patterns (CNIC `\d{5}-\d{7}-\d`, email, PK mobile `03\d{2}-?\d{7}`) | Medium (privacy) | Mark column sensitive |

### 10.2 Data Health Score (0–100)

The score is deterministic. It is calculated on the active sheet as it currently stands.

```
C  Completeness       = 1 − missing_cells / total_cells
U  Uniqueness         = 1 − duplicate_rows / total_rows          (exact duplicates beyond first occurrence)
T  Type consistency   = mean over columns of (values matching the column's dominant type / non-missing values)
F  Format consistency = mean over applicable columns of (values in the canonical format / non-missing values)
     • text/category columns: no leading/trailing/repeated spaces AND label not a case/space variant of a more frequent label
     • date columns: value in the column's dominant date format and not ambiguous-unresolved
     • numeric columns: value stored as a real number (not numeric text)

Score = round(100 × (0.35·C + 0.20·U + 0.25·T + 0.20·F))
Bands: 90–100 Excellent · 75–89 Good · 50–74 Needs attention · 0–49 Poor
```

- Columns that are completely empty count towards C but are left out of T and F.
- If a sheet has no data rows, no score is shown. The app says "Not enough data to score."
- The breakdown (C, U, T, F as percentages, plus their weights) always appears next to the score.
- **Stated limitations, shown in the UI:** the score measures structural quality only. It does **not** measure whether values are true, accurate or complete in a business sense. A file can score 100 and still contain wrong numbers. Key duplicates and outliers do not lower the score because they may be legitimate.

## 11. Cleaning operation definitions

Every operation has a typed parameter schema, a preview (affected rows + before/after samples) and an audit record. Operations apply in the order the user adds them. "Destructive" means a confirmation dialog is required.

| # | Operation | Parameters | Behaviour | Destructive |
|---|---|---|---|---|
| 1 | Remove exact duplicate rows | `keep: first\|last` | Drops rows identical in all columns | Yes |
| 2 | Detect / remove duplicates by key | `key_columns[]`, `mode: flag\|remove`, `keep: first\|last` | `flag` adds a boolean column `is_duplicate_key`. `remove` drops repeats. Defaults to `flag` because a repeated ID is not always a duplicate. | Yes (remove only) |
| 3 | Trim whitespace | `columns[]` (default all text) | Strips leading/trailing whitespace including non-breaking spaces | No |
| 4 | Normalise repeated spaces | `columns[]` | Collapses runs of whitespace into one space | No |
| 5 | Standardise capitalisation | `columns[]`, `style: upper\|lower\|title\|sentence` | Changes case only | No |
| 6 | Normalise category labels | `column`, `mapping` (auto-proposed: variants → most frequent spelling, editable) | Replaces variants with the chosen canonical label. The user reviews the proposed map. | No (overwrites, confirmed via map review) |
| 7 | Convert numeric text to numbers | `columns[]`, `decimal: .\|,`, `strip: currency, %, thousands`, `parentheses_negative: bool` | Parses to numbers. Failures stay missing and are counted, with raw values kept in the failure report. | No |
| 8 | Normalise date formats | `column`, `interpretation: DMY\|MDY\|YMD\|excel_serial_1900\|excel_serial_1904`, `output: date\|datetime` | Parses using **only** the confirmed interpretation. ISO `YYYY-MM-DD` and real Excel date cells are always unambiguous. | No |
| 9 | Identify invalid dates | `column` | Adds a boolean column `<col>__invalid_date` and a failure list. Does not change values. | No |
| 10 | Detect missing values | `columns[]`, `extra_null_tokens[]` | Converts null tokens to real missing values and reports counts | No |
| 11 | Handle missing values | `column`, `strategy: leave\|drop_rows\|fixed\|median\|mean\|mode`, `value` (for fixed) | Median and mean apply only to numeric columns, and mode only to categorical. **Never fills with zero unless the user explicitly enters 0 as the fixed value.** | Yes (drop_rows / fills) |
| 12 | Remove completely empty rows | — | Drops rows with every cell missing | Yes |
| 13 | Rename columns | `{old: new}` | New names must be unique and non-empty | No |
| 14 | Reorder columns | `order[]` | A permutation of the existing columns | No |
| 15 | Remove columns | `columns[]` | Drops the columns. They come back with undo or reset. | Yes |
| 16 | Detect possible outliers | `column`, `method: iqr\|zscore`, `threshold` (default IQR 3.0, z 3.5) | Adds a boolean column `<col>__outlier`. **Never deletes.** | No |
| 17 | Flag inconsistent data types | `column` | Adds `<col>__type` with each value's detected type, for review and filtering | No |

**Date handling (rules)**

1. Accepted inputs: DD/MM/YYYY, MM/DD/YYYY, YYYY-MM-DD (with `/`, `-` or `.` separators, 2- or 4-digit years), date-times with `HH:MM[:SS]`, native Excel date cells, and Excel serial numbers (only when the user chooses that interpretation).
2. For each date-like column the app reports evidence: values valid only as DD/MM (first part > 12), valid only as MM/DD (second part > 12), and ambiguous ones (both parts ≤ 12).
3. **The app never guesses.** If any ambiguous value exists and no rule is set, normalisation is blocked and the user is asked, for example: *"03/04/2026: does it mean 3 April 2026 or 4 March 2026?"* The evidence counts are shown, and the default selection is the reading the evidence supports, but the user has to confirm it.
4. If the evidence conflicts (values exist that are valid only as DD/MM *and* others valid only as MM/DD), the column is flagged as mixed. The rows that contradict the chosen rule are reported as failures and never silently changed.
5. A dataset-level rule (for example "all slash dates are DD/MM") can be set once and applied to all columns. It is stored on the session and in the audit log.
6. Raw values are kept in the original data and the failure report. Dates display in DD/MM/YYYY by default, and exports write real Excel dates.

## 12. AI behaviour and limitations

### 12.1 Architecture
```
question ─► interpreter (Groq if configured, else local rules/guided builder)
         ─► {operation, params} validated against the allowlist + real columns
         ─► executed by backend functions (Pandas) ─► structured result (verified)
         ─► optional explanation by Groq, given ONLY the structured result
         ─► explanation checker: every number/date/label must appear in the result; else rejected
```
- No LLM-generated code or SQL is ever run. The only way the LLM output can act is by choosing one operation from the allowlist with validated parameters.
- AI calls have a 20 s timeout. On any provider error (no key, timeout, rate limit, invalid JSON), the local interpreter or template explanation takes over and a visible notice says so.

### 12.2 Allowlisted analytical operations
| Operation | Parameters | Example question |
|---|---|---|
| `count_rows` | filters | "How many records are there?" |
| `aggregate` | measure, agg, filters | "What is the total amount?" |
| `group_rank` | group_by, measure, agg, order, top_n, filters | "Which category has the most records?" |
| `time_trend` | date_col, grain, measure, agg, filters | "Show the trend over time." |
| `extreme_period` | date_col, grain, measure, agg, max\|min | "Which month has the highest sales?" |
| `compare_groups` | group_by, values[2..5], measure, agg | "Compare two departments." |
| `distribution` | numeric column, bins | "How are claim amounts distributed?" |
| `correlation` | two numeric columns (Pearson, n reported) | "Is age related to claim amount?" |
| `missing_summary` | — | "Which columns contain missing values?" |
| `duplicate_summary` | key_columns optional | "Are there duplicates?" |
| `column_profile` | column | "Describe the Region column." |
| `outlier_summary` | numeric column | "Explain the anomalies." |
| `chart_suggestions` | — | "Suggest the best charts for this dataset." |
| `quality_explain` | issue code(s) | "Why is my score low?" |

### 12.3 Privacy rules for AI
- Not sent by default: raw rows, cell values, file contents and file names.
- Sent only when AI is on: the question, column names (unless switched off, in which case `col_1…` aliases are used and mapped back locally), column types, and the **aggregated** result of the executed operation.
- Category labels in aggregated results (for example city names) are sent only for columns not marked sensitive. Sensitive columns (Q16 or user-marked) are never named or valued in AI payloads, and operations that group by a sensitive column return results locally with no AI explanation.
- Row-level content needs an explicit per-session opt-in with a warning. The MVP offers no feature that needs it, so the opt-in is left out of the MVP.
- The API key stays on the server and is never sent to the browser or written to logs.

### 12.4 Chart recommendation rules (deterministic)
- date + numeric → line (sum by month, or by day if the span is under 62 days)
- low-cardinality category (≤ 12) + numeric → bar (sum, sorted descending, top 10)
- low-cardinality category alone → donut (count; only if ≤ 6 categories, otherwise bar)
- numeric alone → histogram
- two numerics → scatter (sampled to 2,000 points, and the sample is disclosed)
- KPIs: row count, plus sum and average of the first 1–3 numeric measures
Column names are never used to assume business meaning. Recommendations say "Amount looks numeric", not "Revenue".

### 12.5 Limitations (shown in the UI)
AI interpretation can misread a question. The computed operation and parameters are always displayed so the user can check them. The AI cannot see the data, cannot do forecasting, and cannot answer questions outside the allowlist.

## 13. Security and privacy requirements

| Area | Requirement |
|---|---|
| Upload validation | Extension allowlist plus content check, streamed size limit, uncompressed-size limit for xlsx, row/column/cell limits, parse timeout |
| Storage | Generated UUID file names in a private directory outside the web root. The client's file name is used only for display, after sanitising. Paths from the client are never used. |
| Path traversal | All file access goes through a storage layer that resolves paths and checks they stay inside the storage root |
| Ownership | Every dataset, session and export belongs to a workspace. All endpoints check ownership on the server (403/404 otherwise). The workspace cookie is HttpOnly, SameSite=Lax, random and server-issued. **It is not authentication.** |
| Authentication | Local-only mode for the MVP. **Public deployment with private data is blocked until real authentication and per-user isolation are built (out of MVP scope).** |
| Input validation | Pydantic schemas on every endpoint. Column names are validated against the session's columns. Enumerated operations and aggregations only. |
| Formula injection | Escaping on Excel export (FR-6.5). Formulas in uploads are never evaluated. |
| CORS | Allowed origins come only from configuration. Same-origin by default, through the frontend proxy. |
| Rate limiting | In-memory per-workspace limits on upload, profile, export and AI endpoints |
| Errors | Generic error messages with an error ID. No stack traces in responses. Details go to server logs without cell values. |
| Secrets | Environment variables only. `.env` is ignored by git and `.env.example` is provided. |
| Dependencies | Pinned versions. `pip-audit` and `npm audit` run as part of testing. |
| Exports | Accessible only with ownership and a short-lived link. Deleted after 24 h. |
| Retention | Automatic expiry (default 7 days), "Delete all my data", and the cleanup task |
| Sensitive data | Personal-identifier detection (Q16). Development and tests use **synthetic data only**. No claims of compliance with HIPAA or Pakistan's data-protection rules are made. |
| Logging | Request metadata, durations and error codes only. Never cell values, file contents or AI payloads. |

## 14. Edge cases

- Empty file, a header-only file, a sheet with only a title row, or a workbook with only empty sheets
- Corrupted ZIP, a file renamed to the wrong extension, a truncated upload
- Password-protected or encrypted xlsx/xls
- CSV in UTF-16, a Windows-1252 file with `£` or `é`, mixed line endings, a semicolon delimiter, quoted fields containing newlines
- Duplicate, blank or very long headers, and headers that are numbers or dates
- Merged cells (the first cell keeps the value and the rest become missing, which is reported)
- Formulas without cached values, error cells (`#DIV/0!`, `#REF!`, which are treated as missing and reported)
- A column that is entirely missing, a single-row sheet, a single-column sheet
- Very wide sheets (500+ columns) and very long text cells (> 32,767 characters are truncated on Excel export, with a warning)
- Mixed date formats and ambiguous dates in one column, the 1904 date system, dates before 1900, two-digit years (rule: 00–69 → 2000s, 70–99 → 1900s, as Excel does, and disclosed)
- Numbers with Pakistani lakh grouping (`12,34,567`), negatives in parentheses, `%` values, trailing `-`
- Every value identical (IQR = 0, so no outliers are reported), a group-by with more than 500 categories
- Undo with an empty history, reset when already original, an operation that affects 0 rows (the user is told and nothing is recorded)
- A filter that leaves 0 rows (empty state), and a chart whose configuration became invalid after a column was removed or renamed (the widget shows "needs reconfiguring")
- Session expiry while the session is open (clear message, return to Workspace)
- AI: no key, timeout, rate limit, malformed JSON, references to columns that don't exist, prompt-injection text inside cell values or column names (column names are passed as data and cell values are never sent)

## 15. Acceptance criteria

The MVP is accepted when all of the following are **demonstrated and verified by executed tests or recorded manual checks**:

1. A user can upload `.xlsx`, `.xls` and `.csv` files up to the configured limit and sees real progress. Invalid, empty, corrupted and password-protected files are rejected with specific messages.
2. A user can select any worksheet, including hidden ones (labelled), and choose the header row.
3. The preview matches the source file (verified against the synthetic datasets in tests).
4. Each issue type Q01–Q16 is detected on a dataset designed to contain it, with exact affected-row counts verified by tests.
5. The health score matches the documented formula, checked by a hand-calculated test case.
6. Each of the 17 cleaning operations produces the expected result in unit tests. The preview count equals the applied count.
7. Ambiguous dates are never converted without user confirmation (a regression test).
8. After any sequence of operations, **Reset** gives data identical to the original upload, and **Undo** restores the previous state exactly.
9. The audit log records every apply, undo, reset and export, in order.
10. Users can create, configure, filter and reorder every chart type. Dashboard values equal independent Pandas calculations in tests.
11. With no AI key, every analytical operation works through the local interpreter or guided builder.
12. With a Groq key, questions map to allowlisted operations, explanations are verified, and a test confirms that fabricated numbers are rejected. Without a real key, this is tested with a mocked provider and clearly reported as such.
13. The Excel export has the 4 required sheets, its totals match the dashboard, and formula-like text is escaped.
14. The PDF export contains every required section and the time zone is shown.
15. Pytest, Vitest and Playwright suites pass, and the counts are reported from real runs.
16. The app starts locally with the documented commands and with `docker compose up`.
17. Key screens work at 360 px, 768 px and 1280 px (checked with Playwright screenshots).
18. Security tests pass: malicious file names, path traversal, access to another workspace's data, oversized upload, formula injection.
19. No control in the UI is a placeholder.

## 16. Explicitly excluded from the MVP

- User accounts, sign-up/login, teams, roles, sharing, and public multi-tenant hosting (designed for, but built later)
- Payments, subscriptions, usage billing
- Database, API, Google Sheets or cloud-drive connectors
- Joining or merging multiple files or sheets, pivot-table builder, custom formula columns
- Manual cell-by-cell editing in the grid
- Forecasting, machine-learning models, automated root-cause analysis
- Scheduled or recurring reports and email delivery
- PowerPoint export, editable dashboard sharing links
- Urdu interface (planned later), RTL layout
- Sending row-level data to the AI
- `.ods`, `.xlsb`, JSON and Parquet uploads
- Native mobile apps (the web app is responsive instead)

## 17. MVP definition of done

- All acceptance criteria in section 15 are met and evidenced (test output, screenshots, benchmark table).
- SPEC.md, PLAN.md, CLAUDE.md, README.md and `.env.example` are complete and current.
- Alembic migrations create the schema from scratch.
- Synthetic sample datasets for retail sales, HR attendance, financial transactions (PKR), insurance claims (no personal identifiers) and hospital utilisation (no patient identifiers) are committed, each with a generator script and a README of deliberately planted issues.
- `docker compose up` starts a working app from a clean checkout.
- `pip-audit` and `npm audit` show no unresolved high or critical findings, or any remaining ones are documented with a justification.
- Known limitations and the next five recommended features are documented.
- Every completed milestone has been committed and pushed to the project branch after your approval.
