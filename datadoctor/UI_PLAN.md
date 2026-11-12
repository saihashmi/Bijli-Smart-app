# DataDoctor AI — Premium UI/UX Upgrade: Implementation Plan (UI_PLAN.md)

| | |
|---|---|
| Status | **Draft v1.0, awaiting product-owner approval** |
| Based on | `DESIGN_SPEC.md` v1.0 — Direction A "The Refinery" chosen by the product owner (2026-11-13) |
| Branch | `ccr-47143d17-8h5n17` |

## Assumptions to confirm

The product owner answered "A" (direction). The other four open questions from the proposal are assumed as recommended. **Say so if any of these is wrong; approving this plan confirms them.**

| # | Question | Assumed |
|---|---|---|
| 1 | Landing direction | **A — The Refinery** (confirmed) |
| 2 | Order of work | **(a)** Design first for existing screens; Dashboard, AI Analyst and Export are built directly in the new design, merged with functional milestones M9–M13 |
| 3 | New libraries | `three`, `@react-three/fiber`, `@react-three/drei`, `motion`, `recharts` (all free, open source). Dev only: `@axe-core/playwright`, `lighthouse` |
| 4 | Backend additions (read-only, no database change) | Affected-rows endpoint, per-cell flags on the rows endpoint, compact missing-value map in the profile |
| 5 | Primary button colour | Fill `#2563EB` for readable white text; `#3B82F6` for glows, links on dark and charts |

## Rules for every milestone

- One milestone at a time: implement → run → test → fix → show screenshots → update CLAUDE.md → commit and push → ask **"Keep going?"**
- Existing behaviour must keep working: the full existing suites (Pytest, Vitest, Playwright) are run at the end of every milestone, and any test that changes is listed in the report with the reason.
- No fake data, no dead controls, no invented progress. Synthetic examples are labelled.
- Each milestone is sized to be under one hour of build time. If one overruns, it is split and reported rather than rushed.
- Screens are checked at **375, 768, 1280 and 1440 px** (the Playwright projects change from 360/768/1280 to 375/768/1280/1440 in U1).

---

## Stage 1 — Foundation

### U1. Design tokens and theme
**Build:** Replace the colour tokens in `globals.css` with the DESIGN_SPEC §4 set (dark "Midnight" and light "Executive Light"); gradients, radii, shadows, motion durations/easing, focus ring; typography scale; dark default on the landing page, system default in the workspace. Update existing components only where a token name changes.
**Tests:** Contrast unit test extended to every new text/background pair in both themes (WCAG AA). Playwright projects updated to four widths. Full existing suites.
**Accepted when:** all contrast pairs pass; every existing page renders in both themes with no unreadable text (screenshots of 6 pages × 2 themes reviewed); no horizontal overflow at four widths.

### U2. New building blocks
**Build:** Tooltip, Dialog, DropdownMenu, Popover, SegmentedControl, StatTile, SeverityBadge (icon + label + colour), EmptyState; Motion installed with a shared `Reveal` wrapper that turns itself off under reduced motion.
**Tests:** Vitest for SeverityBadge labels and the reduced-motion switch; Playwright keyboard checks (Tab, Enter, Escape) on a small internal demo route used only in tests.
**Accepted when:** each component is keyboard operable with a visible focus ring in both themes.

### U3. App shell
**Build:** Collapsible glass sidebar (state remembered; icons-only when collapsed; "Overview" replaces "Workspace" as the label, same route), top bar with dataset chip (file, sheet, rows × columns, version), real processing-status indicator driven by in-flight requests, theme toggle, "Local mode" badge. Mobile drawer kept.
**Tests:** Playwright: collapse/expand persists across reload; active route marked; drawer on mobile; skip link still works; status indicator appears during a real profile request.
**Accepted when:** navigation works by mouse and keyboard at four widths; no blur is applied behind tables.

### U4. Command palette
**Build:** `Ctrl/⌘ K` palette: go to a screen, open a recent session, start a cleaning tool, switch theme. Only real actions are listed.
**Tests:** Playwright: open with keyboard, filter, run "Go to Settings", open a recent session, Escape closes and returns focus.
**Accepted when:** every listed command performs its action; unavailable commands (no session open) are not shown.

## Stage 2 — Landing page

### U5. Landing structure and static sections
**Build:** New landing layout, dark by default: glass navigation, hero text and CTAs ("Start Analyzing" → `/upload`, "Explore Features" → `#features`), **static SVG pipeline illustration** in the hero slot (this is also the permanent fallback), Section 7 (Who it's for), Section 8 (final CTA), Section 9 (footer with product links, privacy summary, contact from `NEXT_PUBLIC_CONTACT_EMAIL` or hidden, copyright, version from the API).
**Tests:** Playwright: every CTA and link navigates correctly; footer shows the real version; no console errors; four widths, no overflow.
**Accepted when:** the page is complete and attractive with no WebGL at all.

### U6. 3D Refinery hero
**Build:** `three`, `@react-three/fiber`, `@react-three/drei` added. Scene per DESIGN_SPEC §3 (messy stack → diagnostic core → clean panel → rising chart fragments, flow lines, sparse particles), dynamic import with no server rendering, cross-fade from the static illustration, pointer parallax, scroll-linked camera within the hero, pause when off screen or tab hidden, pixel-ratio cap, automatic quality step-down, reduced-motion still frame, fallback on no WebGL / low power / save-data.
**Tests:** Playwright: canvas appears after the headline is visible; navigation works while it loads; with WebGL disabled the static illustration remains and no error is logged; with reduced motion emulated no animation frames are requested after the first render; rendering stops when scrolled away. Build check: the 3D chunk is absent from every workspace route's bundle.
**Accepted when:** all of the above pass, and bundle sizes are recorded (landing first-load JS and the lazy 3D chunk) against the budgets in DESIGN_SPEC §11.

### U7. Transformation story and before/after
**Build:** Section 2: five connected cards (Upload → Diagnose → Clean → Analyze → Export) with a line that draws on scroll and small animated line illustrations. Section 3: draggable before/after spreadsheet comparison with highlighted issues, operable with arrow keys, labelled "Synthetic example data".
**Tests:** Playwright: slider moves by drag and by keyboard and exposes its value to screen readers; the synthetic label is present; reduced motion shows the final state without animation.
**Accepted when:** both sections work at four widths with keyboard only.

## Stage 3 — Existing workspace screens

### U8. Upload Studio redesign
**Build:** Premium drop surface with animated gradient border (static under reduced motion), file icon, byte-accurate progress, validation messages, worksheet selector and header-row picker restyled, file metadata, recent session cards. After "Start analysis": a stage list driven by the real requests (Validating file → Reading worksheets → Reading the sheet → Profiling columns → Detecting issues → Preparing results), indeterminate until each completes, then an animated hand-off to the Data Health Center.
**Tests:** All existing upload tests still pass (selectors updated where needed); new: stages complete in order for a real upload; a failing file stops at the right stage with its message; no percentage is shown for indeterminate stages.
**Accepted when:** every upload behaviour from M4 is intact.

### U9. Backend additions for drill-down and cell states
**Build (backend, read-only):** `GET /api/sessions/{id}/issues/{issue_id}/rows` (paged spreadsheet rows and values for an issue); rows endpoint gains optional per-cell flags (missing, invalid date, duplicate row, changed since original); profile gains a compact missing-value map (columns × up to 50 row buckets). Ownership checks and rate limits as on existing endpoints. Profile schema version bumped.
**Tests:** Pytest: counts from the new endpoint equal the issue's affected-row count for every issue type; flags match an independent calculation; missing map sums equal column missing counts; other workspaces get 404.
**Accepted when:** no existing API response changes shape except by addition.

### U10. Data Health Center redesign
**Build:** Large circular gauge with a single reveal and band label; methodology panel; six metric tiles (rows, columns, missing values, duplicate rows, invalid values, inconsistent formats); missing-value heatmap; column completeness bars; severity breakdown; data-type distribution; column quality distribution; issue cards with SeverityBadge and **"Show affected rows"** drill-down (dialog with a paged table); column profile cards restyled.
**Tests:** Existing health tests pass; new: tile values equal the API values; heatmap cell tooltips match the map; drill-down row count equals the issue's count; gauge has a text alternative; reduced motion shows the final gauge immediately.
**Accepted when:** nothing on the page relies on colour alone, verified by reviewing greyscale screenshots.

### U11. Cleaning Studio redesign
**Build:** Three-panel layout on desktop (tools and suggested fixes · data grid · details/preview/history), two panels on tablet, tabbed flow on mobile. Grid: sticky headers, type icons, cell states with legend and tooltips (missing, invalid date, duplicate row, corrected), filter "show only rows with issues", arrow-key cell navigation with a visible selection. Undo/Reset/Apply restyled; audit timeline kept.
**Tests:** All existing cleaning tests pass; new: cell states match the API flags; keyboard navigation moves the selection; issue filter count equals the API count; corrected marker appears after an apply and disappears after undo.
**Accepted when:** every M7/M8 behaviour is intact and the grid stays smooth on the 200,000-row benchmark file (scroll test recorded).

## Stage 4 — New screens built in the new design (merged with functional milestones)

### M9. Analytics engine (functional, as in PLAN.md)
**Build:** `analytics.query()` (count, sum, average, min, max, median, distinct; group-by; date grain; filters incl. date range; sort; top-N; 500-point cap), aggregation/type compatibility rules shared with the frontend, chart recommendations (DESIGN_SPEC §8 rules), dashboard configuration persistence.
**Tests:** Every aggregation compared with an independent pandas calculation; date-range edges; distinct counts; empty results; invalid configurations rejected.

### M10a. Chart theme and chart components
**Build:** `recharts` added. `lib/chart-theme.ts` (series colours by stable key, axes, grid, tooltip, legend, number formatting, three dashboard themes as token sets). ChartCard, ChartTooltip, ChartLegend, KPI card, and the ten chart types, each with a generated text summary and "View as table".
**Tests:** Vitest: stable colour assignment (same key → same colour across renders and charts), number formatting (1.2M, 45k, PKR), summary text; Playwright: values in tooltips equal API values.

### M10b. Dashboard Studio
**Build:** 12-column grid, widget editor (type, X, Y, aggregation, group, date grain, sort, top-N, title), recommended first dashboard, dashboard filters and date range, legend toggling, click-to-filter drill-down, reorder by drag and by keyboard, PNG export per chart, theme switcher (Midnight Intelligence, Executive Light, Minimal Analytics), saved layout.
**Tests:** Playwright: build a chart, change aggregation, filter, drill down, reorder, switch theme, reload persists; displayed values equal API values; empty states show reasons.

### M11–M12. AI Analyst (functional + design)
**Build:** Allowlisted operations, local interpreter, guided builder, optional Groq with verified explanations and privacy filter (as in PLAN.md), in the DESIGN_SPEC §9 layout: conversation, dataset context panel, answer cards with four labelled parts (Computed result, How it was calculated, AI explanation, Suggested next questions), neutral "can't answer" card.
**Tests:** As PLAN.md M11/M12 (including fabricated-number rejection with a mocked provider), plus Playwright checks that each part of an answer card is labelled and that AI text is never shown without a computed result.

### M13. Exports and Export Center (functional + design)
**Build:** Excel (4 sheets) and PDF exports with formula-injection protection and signed downloads (as in PLAN.md), Export Center with option cards, live outline and recent exports; PDF uses the Executive Light chart theme.
**Tests:** As PLAN.md M13 (totals equal the query engine, escaped cells, PDF sections), plus Playwright download checks.

## Stage 5 — Landing showcases

### U12. Product, AI and dashboard showcases
**Build:** Section 4: tabbed frame with **real screenshots** of the four screens, produced by a Playwright script from the running app with a bundled synthetic dataset (script committed so they can be regenerated). Section 5: replay of one question with numbers computed by the real engine from the synthetic dataset at build time, marked as a demonstration. Section 6: four charts in the chart theme from the same dataset. All labelled "Synthetic example data".
**Tests:** A test recomputes the showcase numbers with the engine and fails if the page shows anything else; screenshots regenerate without error.

## Stage 6 — Validate and ship

### U13. Accessibility and responsive validation
**Build/Run:** `@axe-core/playwright` on every page in both themes; keyboard-only walkthrough test (upload → health → clean → dashboard → analyst → export); reduced-motion pass; screenshots at four widths for every page; fix findings.
**Accepted when:** no serious or critical axe violations; no horizontal overflow; findings and fixes listed in the report.

### U14. Performance validation
**Build/Run:** Bundle sizes from the build; Lighthouse (dev tool) on the production build for the landing page, Data Health Center and Dashboard Studio; hero frame-time sampling (labelled as software rendering in this environment); fixes for anything over budget.
**Accepted when:** measured numbers are recorded in README and CLAUDE.md next to the budgets, with any miss stated plainly.

### M14–M16. Remaining functional milestones (as in PLAN.md)
Security, edge-case and regression testing (including the known flaky browser test); final polish; Docker, README, deployment preparation. Nothing is deployed without approval.

---

## Order and dependencies

```
U1 → U2 → U3 → U4
          └→ U5 → U6 → U7
U3 → U8 → U9 → U10 → U11
U9, U2 → M9 → M10a → M10b → M11–M12 → M13 → U12 → U13 → U14 → M14–M16
```

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Restyling breaks existing tests or behaviour | Full suites after every milestone; selectors use roles and test ids, not styles |
| 3D hurts load time or low-end devices | Lazy chunk, static first paint, quality step-down, fallback, budgets measured in U6 and U14 |
| Frame rates measured here are not representative | Software rendering is stated with every number; the step-down logic is tested functionally instead |
| Dark default lowers readability | Contrast test on every token pair; glass never behind tables |
| Scope growth (many screens, many visuals) | One milestone at a time with approval; anything beyond DESIGN_SPEC needs your sign-off |
| Showcases drift from the real product | Screenshots and numbers are generated from the running app by script and checked by a test |

## Definition of done

All milestones above accepted; all suites passing from real runs; DESIGN_SPEC.md, UI_PLAN.md, CLAUDE.md and README current; measured accessibility and performance results documented; every item in the brief's 15-point verification list checked and reported individually.
