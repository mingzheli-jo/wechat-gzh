# Frontend Polish — Editorial Swiss

**Date:** 2026-05-06
**Scope:** Frontend design upgrade. One small backend change in Round 3 (additive: per-role daily cost breakdown in `/api/usage/summary`).
**Branch:** master (direct commit; personal solo project, no remote)

## Direction

The current design system is Swiss/International — clean, neutral, "internal-tool" aesthetic. This spec keeps the direction but pushes it one notch toward **editorial Swiss**: typography is more deliberate, numbers are typeset like a data sheet, hairline rules replace some card chrome, and three pages get a "signature moment" that anchors the visual identity.

**The thing the user should remember:** *the numbers look typeset.*

**What does NOT change:**
- Color tokens (warm neutrals, near-black accent, status pastels)
- Font families (DM Sans + DM Mono)
- Spacing scale, radius, shadow tokens
- Information architecture / routing / page boundaries

**What DOES change:**
- How tokens are applied (consistency, hierarchy, mono usage on numbers)
- Three core pages get a focal "data display" treatment
- Card-on-card visual weight reduced via hairlines

---

## Part A — System-Level Polish

Cross-cutting changes that touch every page.

### A1. Tabular numerals + DM Mono on display numbers

**Rule:** Any number whose value the user reads (score, count, cost, token total, percentage, file size) renders in `var(--font-mono)` with `font-variant-numeric: tabular-nums`.

**Exception:** Inline numbers inside running prose stay in DM Sans (e.g., "12 篇文章" inside a paragraph).

**Audit targets:**
- `DraftDetail.tsx` — score numbers (currently DM Sans)
- `Drafts.tsx` — list counts
- `Library.tsx` — to be added (status counts in new status bar)
- `Settings.tsx` — already partially correct (usage table mono); hero numbers need promotion to mono

### A2. Hairline rule treatment

Replace some `Card`-on-`Card` nesting with 1px hairlines (`border-bottom: 1px solid var(--color-surface-3)`).

**New shared component:** `<HairlineRule>` — a 1px `<hr>` styled with token color and zero margin (callers control spacing).

**Apply where:** between sections within a single conceptual surface (e.g., DraftDetail review report dimensions, Settings dashboard between hero/chart/table).

**Do NOT apply where:** between unrelated cards (those should keep card boundaries).

### A3. Eyebrow label component

Currently the pattern `text-xs / weight-semi / uppercase / letter-spacing 0.06em / color ink-3` is reimplemented inline ~12 times.

**New shared component:** `<EyebrowLabel>` — accepts `children` and optional `as` prop (default `<p>`, supports `<h2>` etc. for semantic correctness).

### A4. Hairline progress bar

Current 3px progress bar in `DraftDetail` looks like a UI gauge. Replace with 1px hairline against `--color-surface-3` background, filled by 1px black bar to score percentage. More "ruler" / "data sheet" than "progress widget."

**Reusable component:** `<HairlineMeter score={n} max={100} />`

### A5. Score number components

Current `ScoreRing` is named `Ring` but renders text. Confusing.

- **Rename / refactor:** `<ScoreNumber size="sm|md|lg|hero" score={n}>` — text-only, color follows score band, tabular mono.
- **Add:** `<ScoreDial score={n}>` — actual SVG ring (used only on the DraftDetail hero overall score). 1px stroke, no fill, with score band color.

### A6. Focus / hover states centralized

Currently every input does its own `onFocus={e => e.currentTarget.style.borderColor = '...'}` inline.

- **Add token:** `--ring-focus: 0 0 0 2px var(--color-ink-2);`
- **Add CSS class** in `index.css`: `.input-base:focus-visible { box-shadow: var(--ring-focus); border-color: var(--color-ink); }` etc.
- **Refactor:** `Input.tsx` and ad-hoc inputs (Library textarea, DraftDetail title input, Settings provider form) use the class instead of inline handlers.

### A7. Tailwind arbitrary-values audit

Commit `427b731` already revealed Tailwind arbitrary values like `bg-[#xxx]` get stripped in production builds. Audit all `frontend/src/**/*.tsx` for any remaining `bg-[`, `text-[`, `border-[`, `[`, `]` Tailwind arbitrary syntax. Replace with inline `style={{ ...token... }}` or define a token.

**Method:** ripgrep `\b(bg|text|border|ring|from|to|via|fill|stroke)-\[` across `frontend/src/`.

### A8. Acceptance for Part A

- All 6 pages render with no inline color hex codes (search: `#[0-9a-f]{3,6}` outside `tokens.css` should be empty)
- All "display numbers" use mono + tabular
- Eyebrow labels reduced to single component import
- Tailwind arbitrary values all gone
- Existing Playwright suite still passes (no test changes needed for A — purely cosmetic)

---

## Part B-1 — DraftDetail signature moment

### Current state

Right sidebar (320px wide) holds:
1. Publish action card
2. Review report card with `ScoreRing` text + 4 dimension rows (label · score · 3px progress bar · bullet issues)
3. Status badge box

Visual: flat. Score "ring" is misleading text. The 4 dimensions sit in a stack with thin progress bars; issues are plain bulleted lists.

### Target: Editorial Scoresheet

Re-render the review report card as an editorial data spread, not a UI panel.

**Layout (top to bottom inside sidebar):**

1. **Hero score block:**
   - Right-aligned `<ScoreDial score={overall_score}>` — 96px SVG ring, 1px stroke, score-band color, with the number `{overall_score}` centered in `--text-3xl` (44px) DM Sans semi-bold, tabular, letter-spacing -0.04em.
   - Below the dial, right-aligned: small mono caption `4 dimensions / reviewed by {provider}` (provider name pulled from binding). If unknown, fallback to just `4 dimensions reviewed`.
   - 1px `<HairlineRule>` below caption.

2. **4 dimensions, vertical stack** (per dimension):
   - Row 1: `<EyebrowLabel>` left (e.g., `合规 / COMPLIANCE`) + `<ScoreNumber size="md">` right (28px DM Mono tabular).
   - Row 2: `<HairlineMeter score={n} />` (1px tall, full width).
   - Row 3: issues — rendered as **editorial pull-quotes**, NOT bullets:
     - Italic body face (DM Sans regular italic, 13px)
     - Each issue prefixed by an em-dash `—` hung in the left margin (negative `text-indent`)
     - Color `--color-ink-2`
     - Show first 2 issues by default; if `>2`, render an inline `+{n} more` toggle.
   - Spacing between dimensions: `var(--space-5)`. No horizontal rule between dimensions — the hairline meter inside each dimension provides the separator.

3. **Card chrome change:**
   - Drop the `<Card padding="md">` wrapper. The whole report flows in transparent ground inside the sidebar with vertical spacing alone.
   - Publish action stays as `<Card>` (it's a CTA, deserves a frame).
   - Status badge box stays as `<Card>`.

### Detailed component tasks

- **New:** `<ScoreDial score={n} size={number}>` — SVG circle with stroke-dashoffset for fill, score-band color via inline style.
- **Replace:** `ScoreRing` callsites → `<ScoreNumber>`.
- **Replace:** dimension row markup → uses `<HairlineMeter>` and the new pull-quote issue renderer.

### Acceptance for B-1

- DraftDetail loads, shows hero dial, 4 dim rows
- Score color bands correct: 80+ green-fg, 60-79 warn-fg, <60 failed-fg
- Issues render as italic em-dash pull-quotes; "+N more" toggles correctly; if 0 issues, the section collapses with no empty space
- Existing E2E test for DraftDetail still passes (DOM structure changes; selector updates may be needed — fix in same commit)

---

## Part B-2 — Settings cost dashboard signature moment

### Current state

`UsageDashboard` inside `Settings.tsx`:
1. Three equal-weight summary cards (cost / prompt tokens / completion tokens)
2. 64px-tall monochrome bar chart with 30 daily bars
3. By-role table

### Target: Hero number + role-stacked chart + refined table

#### B-2.1 Hero number block (replaces 3 equal cards)

Layout: 2-column grid.

- **Left column (60% width):**
  - `<EyebrowLabel>` — `近 30 天总成本（估算）`
  - Big number — `--text-3xl` × 1.6 (~70px) DM Sans semi-bold, tabular, letter-spacing -0.04em. Format: `$0.0042` (4 decimals; if cost ≥ $10, drop to 2 decimals).
  - Below, mono caption: `vs 上 30 天 +12.3%` with `+`/`−` color band (green-fg for `−`, failed-fg for `+`; cost going up is bad).
    - To compute delta, fetch `?days=60`, split into two halves; OR add a `previous_total_cost` field to the API. **For v1, do client-side split** to avoid backend changes.

- **Right column (40% width):** Two stacked sub-stats.
  - `Prompt tokens` — 24px mono number with eyebrow label.
  - `Completion tokens` — same.
  - Tight vertical spacing.

- 1px `<HairlineRule>` below the entire block.

#### B-2.2 Stacked bar chart

- Height bumped 64px → 112px.
- Bars stacked by `role` (writer / reviewer / lite). Need backend response to expose per-day per-role breakdown.
  - **Backend change required:** extend `/api/usage/summary` `daily` array entries to include `by_role: { role: cost }` map. **Simple SQL change in `app/api/usage.py`** — group by day AND role.
- Bar colors: writer = `--color-ink` (near-black), reviewer = `--color-ink-3` (mid gray), lite = `--color-ink-4` (light gray). Single coherent grayscale stack — color = role hierarchy.
- Bar width: flex-grow with `2px` gap.
- Empty days: render as 1px tall light gray pill (visible as ground line, not invisible).
- X-axis: every 7 days a tick mark + mono date label below. Today's bar gets a thin top accent line.
- **Hover:** cursor enters a bar → callout popover (absolutely positioned) appears showing `日期 · writer $X · reviewer $Y · lite $Z · total $T`. Use a small triangle pointer on the popover. Mono fonts throughout the popover.
  - Implementation: pure CSS hover with `position: absolute` and pseudo-element pointer; OR React state with `mouseenter`/`mouseleave`. Prefer React state for accuracy (CSS hover stacks awkwardly when bars are 8px wide).
- Below the chart: row with date range on the left + `total: $X` on the right (mono, bold).

#### B-2.3 Table refinements

- Add small color swatch (8px square) before role label, matching chart colors.
- Role cell: switch from `<Badge>` to `<EyebrowLabel>` style.
- Rows: hover background `--color-surface-2`.
- All numeric cells: `tabular-nums` already applied; verify mono usage on cost cell.
- Provider/model cell: pure DM Mono, gray.

### Acceptance for B-2

- Hero number renders correctly with delta (sign + color)
- Stacked bar chart loads with three roles visible (assuming data exists for >1 role)
- Hover callout positions correctly across all bars (including edges)
- Empty days show as ground line, not blank
- Table rows hover-highlight; color swatch matches chart

---

## Part B-3 — Library signature moment

### Current state

Header → 1fr/2fr grid (input panel left, list right). Each list item is a card with border + radius. Bottom sticky action bar appears on selection. Has fade-in cascade and pulse-on-processing.

### Target: Status bar header + de-carded list

#### B-3.1 Status bar (new)

Inserted between page header and the 1fr/2fr grid.

Layout: horizontal flex, 4 stat blocks, equal flex-1.

For each block:
- 32px DM Mono tabular number on top
- `<EyebrowLabel>` below (e.g., `待抓取 / PENDING`)
- Spacing: `var(--space-1)` between number and label

Behaviors:
- `processing` block — when count > 0, the number gets a small `<Pulse>` dot (4px circle) absolutely positioned at top-right, color `--color-processing-fg`, animation pulse 1.2s infinite.
- `failed` block — when count > 0, number color switches to `--color-failed-fg` to demand attention.
- `pending` and `done` — neutral `--color-ink`.

Below the status bar: 1px `<HairlineRule>`.

Counts derived client-side from the existing `/library` query result. No backend change.

#### B-3.2 List de-carding

Per-item card → row with hairline separator.

Changes to each list item's container:
- Remove `border`, `border-radius`, `box-shadow`, `backgroundColor`. Use only `border-bottom: 1px solid var(--color-surface-3)`.
- First item: no `border-top`. Last item: `border-bottom` provides closing line.
- Padding: keep current (`var(--space-4) var(--space-5)`).
- **Selection indicator:** instead of border-color change + box-shadow ring, render a 3px-wide vertical bar absolutely positioned at the row's left edge, color `--color-ink`. Appears via opacity transition.
- **Hover state:** background `var(--color-surface-2)` with 120ms ease.
- Existing fade-in cascade on initial load: keep.
- Existing pulse-on-processing badge: keep (pulse moves into the badge, not the row).

#### B-3.3 Misc

- Bottom sticky action bar: keep verbatim.
- Empty state: keep.

### Acceptance for B-3

- Status bar renders with 4 numbers + correct color states
- Failed count >0 turns red
- Processing count >0 shows pulse dot
- List items have hairline separators, no card chrome
- Selection: left-edge bar appears
- Existing E2E tests pass (selector updates may be needed for the de-carded structure)

---

## Implementation Rounds

Each round = 1 commit. Tests run after each round.

| Round | Scope | Files touched |
|-------|-------|---------------|
| 1 | Part A (system) | `tokens.css`, new components in `components/ui/`, audit pass on all pages |
| 2 | Part B-1 (DraftDetail) | `DraftDetail.tsx`, new `ScoreDial`, `HairlineMeter` |
| 3 | Part B-2 (Settings) | `Settings.tsx`, backend `app/api/usage.py` (add per-role daily breakdown) |
| 4 | Part B-3 (Library) | `Library.tsx` |
| 5 | Test pass | run `pnpm test:e2e`, fix selectors, visual sanity check |

**Backend change in Round 3** is small (one extra GROUP BY in the SQL aggregator + a Pydantic schema field). Out-of-scope for "frontend-only" but unavoidable for the role-stacked chart. If user objects, fall back to a single-color chart for B-2 and skip the per-role breakdown.

## Risks

- E2E selectors will likely break in Rounds 2 and 4 because the DOM structure changes substantially. Acceptable — fix in same commit.
- Hover popovers on a bar chart can be finicky on narrow bars (8px wide). Verify on a 30-day data range; if unstable, fall back to title attribute.
- Tabular-nums on Chinese mixed text can cause spacing oddness; if visual issues appear, scope tabular-nums to numeric-only spans, not full sentences.

## Out of Scope

- Dark mode (tokens.css has only light values; not adding now)
- Mobile responsive polish (current layout fixed-grid; mobile is not a target user)
- Animation choreography beyond what already exists
- Component library extraction (the new components live in `components/ui/`, not a separate package)
