# DataDoctor AI — Premium UI/UX Upgrade: Design Specification (DESIGN_SPEC.md)

| | |
|---|---|
| Status | **Draft v1.0, awaiting product-owner approval** |
| Phase | Design audit + design specification (no application code changed) |
| Applies to | `datadoctor/frontend` (backend additions are listed separately in §12 and need approval) |
| Date | 2026-11-13 |

> **Futuristic on the outside. Professional and productive on the inside.**

---

## 1. Design audit (what exists today)

| Area | Finding |
|---|---|
| Framework | Next.js 15.5 (App Router), React 19, TypeScript, Tailwind CSS v4, shadcn-style components on Radix, Lucide icons, self-hosted Inter, `next-themes`, Sonner toasts, TanStack Virtual |
| Pages built and working | Landing (`/`), Workspace, Upload Studio, Data Health Center, Cleaning Studio (17 operations, preview, undo/reset, history, before/after), Settings |
| Pages that are placeholders | **Dashboard Studio, AI Analyst, Export Center.** Their backend does not exist yet (functional milestones M9–M13 of PLAN.md are not built). |
| Charts | **No charting library is installed yet.** Current visuals are hand-built CSS bars and one SVG gauge. Recharts was planned for M10. |
| Styling system | CSS variables in `globals.css` mapped to Tailwind tokens. Light theme is the default; dark exists. A unit test checks 43 colour pairs for WCAG AA. The current palette (navy `#0F172A`, blue `#2563EB`) differs from the new one in this brief. |
| Components | 46 component files, 17 shadcn-style primitives. No tooltip, dialog, dropdown, popover or command-palette primitives yet. |
| Motion | Only CSS transitions and `tw-animate-css`. No animation library. |
| 3D | None. Headless Chromium in this environment exposes **WebGL2 through SwiftShader (software)**, so a 3D scene can be rendered and tested in Playwright here, but frame-rate measurements taken here will not represent real GPUs. |
| Performance baseline | Landing page first-load JS: 186 kB (from the last production build). Lighthouse is not installed here, so no Lighthouse score has been measured yet. |
| Tests | 87 Playwright tests (360/768/1280 px), 52 Vitest, 184 Pytest. One known flaky browser test (recorded in CLAUDE.md). |
| Must not change | API contracts, database schema, data-processing logic, security behaviour (workspace isolation, upload validation, rate limits), "never guess dates", "AI never calculates", no fake data or dead controls. |

**Three things in the brief that depend on work not yet built** (decision needed, see §13):

1. Dashboard Studio, AI Analyst and Export Center cannot be "redesigned" until they exist (M9–M13).
2. Several requested visuals need small **new read-only backend endpoints** (§12): drilling down to affected records, highlighting problem cells in the grid, a missing-value heatmap.
3. The landing page's product and chart showcases must use either labelled synthetic examples or real in-app previews. Real previews of Dashboard and AI Analyst are only possible after those screens exist.

---

## 2. Three landing-page visual directions

All three use the brief's palette and the same content sections. They differ in the hero concept, mood and cost.

### Direction A — "The Refinery" (data pipeline in depth) — **recommended**

A single coherent 3D scene that reads left to right, exactly like the product story:

**Messy data → Intelligent processing → Clean data → Business insights**

- **Left:** a slightly tilted, disordered stack of translucent spreadsheet panels. Some cells glow amber or red (issues), rows are misaligned, a few cells drift loose.
- **Centre:** a calm "diagnostic core": a glass prism ring with cyan nodes. Loose cells are drawn in along thin connection lines, pass through, and come out aligned.
- **Right:** one clean, perfectly gridded panel in teal/blue, from which chart fragments rise: three bars, a line arc, a donut segment.
- Sparse particles drift along the flow direction. The whole group rotates a few degrees with the mouse.
- On scroll, the camera moves along the pipeline, so the hero hands over naturally to Section 2 (Upload → Diagnose → Clean → Analyze → Export).

*Mood:* precise, confident, explanatory. *Cost:* medium. Simple geometry (planes, boxes, lines, points), instanced, no textures or loaded models.

### Direction B — "Constellation" (data as a living network)

A dark field of glowing nodes joined by lines. A scattered, flickering cluster reorganises into an ordered lattice and then into the outline of a chart as you scroll.

*Mood:* atmospheric, "AI". *Strengths:* light on geometry, very elegant. *Weaknesses:* abstract; it does not say "spreadsheets", so a first-time Excel user may not see what the product does; node networks are a common AI-site cliché.

### Direction C — "Glass Workbench" (the product as the hero)

Three large glass panels floating in perspective showing stylised product screens (health gauge, cleaning grid, dashboard) with soft reflections and a slow orbit.

*Mood:* product-first, premium SaaS. *Strengths:* shows the real product at once. *Weaknesses:* least "3D storytelling"; depends on screens that are not built yet (Dashboard, AI Analyst); text inside 3D panels is hard to keep sharp and accessible.

### Recommendation: **Direction A**

- It is the only one that tells the required story (Messy → Processing → Clean → Insights) as one composition rather than decoration.
- It speaks to the audience: spreadsheets are visibly the subject.
- It is cheap to render (a few hundred instanced boxes and lines), which matters for laptops and phones in the target market.
- It does not depend on unbuilt screens. Direction C's idea is still used, in 2D, for Section 4 (Product showcase).

---

## 3. 3D hero specification (Direction A)

| Item | Specification |
|---|---|
| Libraries | `three`, `@react-three/fiber`, `@react-three/drei` (only the helpers used). Loaded with `next/dynamic` (`ssr: false`), **only on the landing page**. |
| Scene graph | `MessyStack` (3 panels, instanced cells) → `Core` (ring + nodes) → `CleanPanel` → `Insights` (bars, line, donut arc) + `FlowLines` + `Particles`, inside one `Rig` group that receives pointer parallax |
| Geometry budget | ≤ 600 instanced cells, ≤ 150 particles on desktop (≤ 60 on small screens), ≤ 12 draw calls, no textures, no post-processing by default |
| Materials | `MeshBasicMaterial` / `MeshStandardMaterial` with transparency; emissive accents in blue `#3B82F6`, cyan `#22D3EE`, teal `#14B8A6`, violet `#8B5CF6`; issue cells amber/red |
| Motion | Idle float (±0.05 units, 6–9 s loops); cells travel messy → core → clean in an 8 s loop; pointer parallax ≤ 4° with damping; scroll moves the camera along the pipeline through the hero only |
| Rendering limits | Pixel ratio capped at 1.5 (1 on small screens); `frameloop="demand"` when idle; rendering **paused when the hero is off screen or the tab is hidden** |
| Reduced motion | `prefers-reduced-motion: reduce` → no 3D loop: a single static frame (or the static fallback) and no parallax |
| Fallback | No WebGL, a failed context, or low-power hints (`navigator.hardwareConcurrency ≤ 2` or `saveData`) → a **static SVG illustration of the same pipeline**, drawn in the same colours. The page is fully usable without WebGL. |
| Accessibility | Canvas is `aria-hidden`; an adjacent visually-hidden paragraph describes the scene; headline, text and CTAs are normal HTML rendered before the scene loads |
| Loading | Text and CTAs paint first; the static SVG shows immediately and cross-fades to the 3D scene when ready, so 3D never blocks navigation |

Headline: **Your Data Has Potential. Let's Unlock It.** · Subheading as in the brief · CTAs: **Start Analyzing** (→ `/upload`) and **Explore Features** (→ `#features`).

---

## 4. Design tokens

### 4.1 Colour (dark = "Midnight", the default for the landing page)

| Token | Dark | Light ("Executive Light") |
|---|---|---|
| `--bg` | `#080D1B` | `#F8FAFC` |
| `--bg-2` | `#111827` | `#FFFFFF` |
| `--surface` | `#172033` | `#FFFFFF` |
| `--surface-2` (raised) | `#1E2A44` | `#F1F5F9` |
| `--text` | `#F8FAFC` | `#0F172A` |
| `--text-2` | `#94A3B8` | `#475569` |
| `--border` | `rgba(148,163,184,0.15)` | `rgba(15,23,42,0.10)` |
| `--primary` | `#3B82F6` | `#2563EB` |
| `--cyan` | `#22D3EE` | `#0891B2` |
| `--teal` | `#14B8A6` | `#0F766E` |
| `--violet` | `#8B5CF6` | `#7C3AED` |
| `--success` / `--warning` / `--danger` | `#22C55E` / `#FBBF24` / `#F87171` | `#15803D` / `#B45309` / `#B91C1C` |
| `--focus` | `#22D3EE` | `#2563EB` |

Notes:
- White text on `#3B82F6` is 3.7:1, below WCAG AA for normal-size text. Primary buttons therefore use `#2563EB` as their fill in both themes (5.2:1) with `#3B82F6` for glows, borders, links on dark and chart series. This keeps the look and passes AA.
- The existing contrast unit test will be extended to every new token pair in both themes and must pass before any screen is restyled.

### 4.2 Gradients
- `--grad-brand`: `linear-gradient(135deg, #3B82F6 0%, #22D3EE 100%)` (headline accents, key buttons on the landing page)
- `--grad-violet`: `linear-gradient(135deg, #8B5CF6 0%, #3B82F6 100%)` (AI elements only)
- `--grad-hero`: radial glows of blue (top right) and violet (bottom left) at ≤ 18% opacity over `#080D1B`
- Gradients are never used behind body text or data tables.

### 4.3 Typography (Inter Variable, self-hosted)

| Role | Size / line height | Weight |
|---|---|---|
| Display (hero) | clamp(2.5rem, 5vw, 4.25rem) / 1.05 | 700, tracking −0.02em |
| H1 page | 1.75rem / 1.2 | 650 |
| H2 section | 1.25rem / 1.3 | 600 |
| Body | 0.9375rem / 1.55 | 400 |
| Small / labels | 0.8125rem / 1.4 | 500 |
| Data (tables, numbers) | 0.8125rem, tabular numerals | 450 |

### 4.4 Spacing, radii, elevation
- Spacing scale: 4, 8, 12, 16, 24, 32, 48, 64, 96 px.
- Radii: 6 (inputs), 10 (buttons), 14 (cards), 20 (hero panels), full (pills).
- Elevation (dark): level 1 = 1 px border; level 2 = border + `0 8px 24px rgba(2,6,23,0.45)`; level 3 (dialogs) = `0 24px 64px rgba(2,6,23,0.6)`. Light theme uses softer slate shadows.
- **Glass:** `backdrop-filter: blur(12px)` with 60–70% surface colour, used **only** on the top bar, sidebar, dialogs, tooltips and landing cards. **Never behind data tables or charts.**

### 4.5 Motion
- Durations: 150 ms (hover, press), 200 ms (popovers, tabs), 300 ms (dialogs, page section reveal), 600–900 ms (gauge and chart reveal, once).
- Easing: `cubic-bezier(0.22, 1, 0.36, 1)` for entrances, `ease-in` 120 ms for exits.
- Everything honours `prefers-reduced-motion`: reveals become instant, loops stop.
- No animation ever delays a task (data is interactive before reveals finish).

### 4.6 Focus and breakpoints
- Focus ring: 2 px `--focus` + 2 px offset in background colour, visible on every interactive element in both themes.
- Breakpoints: 375 (base), 640, 768, 1024, 1280, 1440.

---

## 5. Animation library choice

**One library: Motion for React (`motion`)** for section reveals, layout transitions, the gauge and the comparison slider. No GSAP (not justified: scroll-linked camera movement is done inside React Three Fiber, and Motion covers the rest). CSS transitions remain for hover/press. This avoids overlapping frameworks.

New dependencies proposed (and nothing else): `three`, `@react-three/fiber`, `@react-three/drei`, `motion`, `recharts` (already in PLAN.md for M10). TanStack Table is **not** added: the existing virtualised grid already covers the need.

---

## 6. Landing page layout

| # | Section | Design | Data honesty |
|---|---|---|---|
| 1 | Hero | Full viewport, `--grad-hero`, glass nav, headline, two CTAs, 3D Refinery on the right (below the text on mobile, reduced) | No numbers |
| 2 | Transformation story | Five cards (Upload, Diagnose, Clean, Analyze, Export) joined by an animated SVG line that draws on scroll; each card has a small animated line illustration | — |
| 3 | Before / after | Draggable comparison slider over one spreadsheet: left messy with highlighted issues, right clean. Keyboard operable (arrow keys), labelled **"Synthetic example data"** | Synthetic, labelled |
| 4 | Product showcase | Tabbed frame showing Data Health Center, Cleaning Studio, Dashboard Studio, AI Analyst. **Real screenshots generated by Playwright from the running app with a synthetic dataset** (regenerated by script, so they never go stale) | Real app, synthetic data, labelled |
| 5 | AI Analyst showcase | A scripted replay of one question ("Which month generated the highest revenue?") showing: question → chosen calculation → computed result → explanation. The numbers come from a bundled synthetic dataset computed at build time by the real engine | Synthetic, labelled; replay marked as a demonstration |
| 6 | Dashboard showcase | Four charts in the DataDoctor chart theme, same synthetic dataset | Synthetic, labelled |
| 7 | Who it's for | Five cards: business analysts, finance, healthcare analysts, HR, small businesses | No claims, no logos |
| 8 | Final CTA | "Stop Cleaning Spreadsheets. Start Making Decisions." → **Launch DataDoctor AI** | — |
| 9 | Footer | Product links, features, privacy summary, contact line from configuration (`NEXT_PUBLIC_CONTACT_EMAIL`, hidden if unset), copyright, app version | No invented address, customers, testimonials or awards |

Sections 4–6 can only show Dashboard and AI Analyst for real once those screens exist. Until then those tabs are left out rather than mocked.

---

## 7. Workspace design system

**Shell**
- **Sidebar** (glass, collapsible to icons, state remembered): Overview, Upload Studio, Data Health, Cleaning Studio, Dashboard Studio, AI Analyst, Export Center, Settings. Active route = filled pill + 2 px accent bar. Mobile: slide-in drawer (kept from today).
- **Top bar** (glass): current dataset chip (file, sheet, rows × columns, version), processing status indicator (real: idle / reading / profiling / applying), command palette button (`Ctrl/⌘ K`: jump to a screen, open a recent session, run a cleaning tool), theme toggle, contextual actions. **No account controls** (no authentication exists) — the "Local mode" badge stays.
- **Content:** 12-column grid, max width 1440, page header component (title, description, actions), consistent card component with three densities.

**Component inventory** (★ = new)

| Group | Components |
|---|---|
| Primitives | Button, Input, Select, Checkbox, Radio, Switch, Tabs, Badge, Card, Alert, Skeleton, Progress, Table, Sheet, AlertDialog, Toast, ★Tooltip, ★Dialog, ★DropdownMenu, ★Popover, ★Command palette, ★SegmentedControl, ★EmptyState, ★StatTile, ★SeverityBadge (icon + text + colour) |
| Data | Virtual data grid (existing, restyled, ★cell states), ★Heatmap, ★RadialGauge, ★CompletenessBars, ★Sparkline |
| Charts | ★ChartCard, ★ChartTooltip, ★ChartLegend, ★chart theme (see §8) |
| Layout | AppShell (restyled), ★TopBar, ★CollapsibleSidebar, PageHeader, ★SplitPane (three-panel Cleaning Studio) |
| Marketing | ★Hero3D + ★HeroFallback, ★StoryFlow, ★CompareSlider, ★ShowcaseFrame, ★ReplayDemo, ★PersonaCard |

**Screen notes**

- **Upload Studio:** large drop surface with a slow animated gradient border (static under reduced motion), file icon, real byte-based progress, validation messages, worksheet selector, file metadata, recent session cards. After "Start analysis", a stage list shows the **real** stages as each request completes: Validating file → Reading worksheets → Reading the sheet → Profiling columns → Detecting issues → Preparing results. Stages are indeterminate spinners that turn into ticks. No invented percentages.
- **Data Health Center:** large circular gauge with one animated reveal and its band label (text, not colour alone); methodology panel (existing formula and limits); six metric tiles (rows, columns, missing values, duplicate rows, invalid values, inconsistent formats); visualisations: missing-value heatmap (columns × row buckets), column completeness bars, issue severity breakdown, data type distribution, column quality distribution; issue cards with severity icon + label, column, rows, suggested action, and **"Show affected rows"** drill-down.
- **Cleaning Studio:** three panels on desktop: left = tools and suggested fixes, centre = data grid, right = issue details / preview / history (tabs). Panels collapse to tabs on tablet and to a stacked flow on mobile. Grid: sticky headers, type icons, cell states: missing = subtle amber tint + dot, invalid date = red corner mark + icon, duplicate row = left stripe + "dup" marker, corrected value = subtle green tint after apply. Each state also has a text tooltip and legend (never colour alone). Arrow-key cell navigation, visible selection.
- **Dashboard Studio, AI Analyst, Export Center:** designed in §8–§9, built with the functional milestones.
- **Settings:** restyled only.

---

## 8. Chart and dashboard styling strategy

**One chart theme module** (`lib/chart-theme.ts`) that every chart reads. No chart sets its own colours or fonts.

| Aspect | Rule |
|---|---|
| Series colours | 1 blue `#3B82F6`, 2 teal `#14B8A6`, 3 violet `#8B5CF6`, 4 cyan `#22D3EE`, then amber `#F59E0B`, rose `#F43F5E`, lime `#84CC16`, slate `#94A3B8`. Light theme uses darker variants for contrast. |
| Stable colours | Colour is assigned **by series key** (category name hashed into the palette order and stored in the dashboard configuration), so "Lahore" is the same colour in every chart and on every render. |
| Semantic colours | Green/amber/red are reserved for status (health, severity, positive/negative change), never for ordinary series. |
| Axes and grid | 12 px Inter, `--text-2`; grid lines horizontal only, 1 px at 8% opacity; no axis lines; ticks abbreviated (`1.2M`, `45k`), full values in tooltips; currency/percent formatting from column type and user setting |
| Tooltip | Glass card, series colour dot, label, formatted value, share of total where meaningful |
| Legend | Interactive: click to hide/show a series, keyboard focusable, never the only way to tell series apart (direct labels where space allows) |
| Motion | One 400–600 ms reveal on first paint; 200 ms on data change; none under reduced motion |
| Accessibility | Each chart has a generated text summary ("Bar chart of Amount by City. Highest: Karachi 1.2M. Lowest: …") and a "View as table" toggle |
| Empty/invalid | Clear reason and a fix suggestion, never a blank frame |

**Chart types:** bar, horizontal bar, line, area, pie, donut, histogram, scatter, KPI card, data table (Recharts + existing grid).

**Smart recommendations** (extends SPEC §12.4, all computed by the backend): date + numeric → line/area; category + numeric → bar; category + count → horizontal bar; single numeric → histogram; two numerics → scatter; part-to-whole → donut only with ≤ 6 categories, otherwise bar. Meaningless combinations are never offered.

**Dashboard grid:** 12 columns on desktop (widgets span 3, 4, 6, 8 or 12), 6 on tablet, stacked on mobile; drag to reorder with keyboard alternative (move up/down); KPI row at the top.

**Interactions:** hover tooltips, legend toggling, dashboard filters, sorting, date-range selection, aggregation selection, click-to-filter drill-down on bar/pie segments, chart export as PNG.

**Dashboard themes** (a theme only swaps tokens; data and configuration are shared):
1. **Midnight Intelligence** — dark, glass cards, glowing accents (default in dark mode)
2. **Executive Light** — white cards, slate text, restrained colour (default in light mode, best for printing and PDF)
3. **Minimal Analytics** — monochrome with a single accent, no card borders, maximum data-ink

**All numbers come from the backend query engine** planned for M9. The frontend never aggregates.

---

## 9. AI Analyst and Export Center design

- **AI Analyst:** a full page in the workspace (not a floating overlay). Left: conversation. Right (collapsible): dataset context (columns, types, sensitive marks, AI status). Each answer is a card with four clearly separated parts, each with its own icon and label: **Computed result** (table/number/chart from the server), **How it was calculated** (expandable: operation, columns, filters), **AI explanation** (violet edge, provider named, only if verified), **Suggested next questions**. Unsupported requests get a neutral "can't answer this" card with the nearest supported alternatives. A subtle violet glow marks AI-generated text only. The typing indicator is three calm dots, static under reduced motion.
- **Export Center:** two large option cards (Excel workbook, PDF report) with included contents, options, a live outline of what the file will contain, and a list of recent exports with expiry. Dashboard theme choice applies to the PDF (Executive Light by default for print).

---

## 10. Responsive behaviour

| Width | Behaviour |
|---|---|
| 375 px | Drawer navigation; top bar shows dataset chip and menu; KPI tiles 2 per row; charts stacked full width; Cleaning Studio becomes Tools → Grid → Details tabs; grid scrolls inside its frame; hero 3D reduced (fewer cells and particles) or static |
| 768 px | Sidebar collapsed to icons; 6-column dashboard grid; Cleaning Studio two panels + tabbed details |
| 1280 px | Full sidebar; 12-column grid; three-panel Cleaning Studio |
| 1440 px | Content max width 1440 with comfortable margins; hero scene larger |

No horizontal page overflow at any width (already an automated check; it will be extended to all new pages).

---

## 11. Accessibility and performance constraints

**Accessibility**
- WCAG 2.1 AA contrast for all text in both themes (automated token test).
- Full keyboard operation, including the comparison slider, command palette, legend toggles, dashboard reordering and grid navigation.
- Severity, cell states and chart series never rely on colour alone (icons, labels, patterns or direct labels).
- 3D canvas hidden from assistive technology with a text alternative; charts have text summaries and a table view.
- Reduced motion respected everywhere. Touch targets ≥ 44 px on mobile.
- Automated: axe checks in Playwright on every page, in both themes.

**Performance budgets** (to be measured and reported, not assumed)

| Item | Budget |
|---|---|
| Landing page JS before 3D loads | ≤ 200 kB gzip first load |
| 3D chunk (three + R3F + drei subset) | Lazy, ≤ 250 kB gzip, loaded after first paint |
| Workspace pages | **No 3D code in any workspace bundle** (enforced by a build check) |
| Largest Contentful Paint (landing, desktop, local) | ≤ 2.5 s, headline is the LCP element (HTML text, not canvas) |
| Cumulative Layout Shift | ≤ 0.05 (the 3D area has a fixed aspect ratio from the first frame) |
| Hero frame time | Target 60 fps on a mid-range laptop; quality steps down automatically if frames exceed 22 ms |
| Charts | ≤ 500 points per chart (existing rule), responsive containers, no re-render on unrelated state |
| Tables | Virtualised (existing) |

Measurement plan: bundle sizes from the Next.js build output; Lighthouse (to be installed as a dev tool) run against the production build for the landing page and two workspace pages; results recorded in `UI_PLAN.md`/README. Frame-rate numbers measured in this environment use software rendering and will be labelled as such.

---

## 12. Backend additions the design needs (read-only, no schema change) — approval required

| Need | Proposed addition |
|---|---|
| "Show affected rows" drill-down from an issue | `GET /api/sessions/{id}/issues/{issue_id}/rows` → paged row numbers and values |
| Highlighting problem cells in the Cleaning Studio grid | Rows endpoint returns per-cell flags for the page (missing, invalid date, duplicate row, changed since original) |
| Missing-value heatmap | Profile adds a compact missing matrix (columns × up to 50 row buckets) |
| "Invalid values" and "inconsistent formats" tiles | Derived from existing issue counts; no new endpoint |
| Processing status in the top bar | Derived from in-flight requests on the client; no new endpoint |
| Dashboard, AI Analyst, Export | Already planned as M9–M13 |

---

## 13. Proposed order of work (decision needed)

The design upgrade and the remaining functional milestones (M9–M16) overlap. Three screens in this brief do not exist yet. Recommended order, so nothing is built twice:

| Step | Work |
|---|---|
| **U1** | Design tokens (dark default + light), contrast tests, new primitives (tooltip, dialog, dropdown, popover, segmented control, stat tile, severity badge, empty state), Motion setup |
| **U2** | App shell: collapsible glass sidebar, top bar with dataset chip, status, theme toggle, command palette |
| **U3** | Landing page sections 1–3 and 7–9 with the 3D Refinery hero, static fallback, reduced-motion support |
| **U4** | Upload Studio redesign with real processing stages and animated hand-off |
| **U5** | Data Health Center redesign: gauge, tiles, heatmap, distributions, drill-down (needs §12 endpoints) |
| **U6** | Cleaning Studio redesign: three-panel layout, cell states, keyboard navigation (needs §12 cell flags) |
| **M9 + M10 (merged with design)** | Analytics engine, then Dashboard Studio built directly in the new chart theme with the three dashboard themes |
| **M11 + M12 (merged with design)** | AI Analyst built directly in the new design |
| **M13 (merged with design)** | Exports and Export Center in the new design |
| **U7** | Landing sections 4–6 using real screenshots and a real computed replay; footer version |
| **M14–M16 + validation** | Security/edge-case tests, accessibility (axe), responsive checks at 375/768/1280/1440, Lighthouse and bundle measurements, Docker, README |

Each step is one or more milestones of under an hour, detailed in `UI_PLAN.md` after this specification is approved.

**Alternative orders:** (b) finish M9–M16 first in the current look, then restyle everything (more total work: three screens get built then rebuilt); (c) design upgrade for existing screens only, and stop there.

---

## 14. What this upgrade will not do

- Change API contracts, database tables, cleaning logic or security behaviour (other than the additive endpoints in §12, if approved).
- Show invented statistics, testimonials, customer counts, logos, awards or addresses.
- Use sample data as if it were the user's data. Every synthetic example is labelled.
- Add account controls, since authentication does not exist.
- Put 3D or heavy blur anywhere in the analytics workspace.
- Add fake progress percentages.
