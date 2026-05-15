---
version: "2.0"
name: CrawlerAI Console
description: >
  Precision data-extraction workspace. Graphite surfaces, chromatic restraint,
  and operator-first ergonomics. Inspired by Linear's exactness, Vercel's
  black/white discipline, and IBM Carbon's enterprise grid — adapted for a
  real-time crawl and extraction console.
category: Developer Tools

# ─── MACHINE-READABLE DESIGN TOKENS ────────────────────────────────────────
# Format follows google-labs-code/design.md spec (alpha).
# Reference syntax: {token.path}

colors:

  # ── Light mode ─────────────────────────────────────────────────
  canvas:          "#F7F8FA"        # Page floor — barely-cool off-white
  canvas-alt:      "#EDEEF2"        # Secondary zones, stripe rows
  panel:           "#FFFFFF"        # Card, dialog, popover surface
  panel-raised:    "#F0F2F7"        # Elevated within a panel (nested inputs, toolbars)
  sidebar:         "#F0F1F5"        # Left rail — slightly more blue-grey than canvas
  border:          "#DDE0E8"        # Default border — cool grey
  border-strong:   "#B8BECF"        # Emphasized border, focused control edge

  text:            "#0A0B0E"        # Near-black — full contrast body
  text-secondary:  "#434857"        # Supporting copy, secondary labels
  text-muted:      "#7E8799"        # Placeholder, helper text, disabled label
  text-on-accent:  "#FFFFFF"        # Text on accent-fill surfaces

  accent:          "#0F172A"        # Primary interactive — deep slate navy
  accent-hover:    "#1E2A45"        # Hover state on primary
  accent-subtle:   "#EEF1F8"        # Tinted wash for row hover, selected state
  accent-fg:       "#FFFFFF"        # Foreground on accent surfaces

  success:         "#047857"        # Emerald — completed, healthy
  success-subtle:  "rgba(4,120,87,0.08)"
  warning:         "#92400E"        # Amber-brown — degraded, slow
  warning-subtle:  "rgba(146,64,14,0.08)"
  danger:          "#BE123C"        # Rose — failed, blocked, critical
  danger-subtle:   "rgba(190,18,60,0.08)"
  info:            "#1D4ED8"        # Blue — running, informational
  info-subtle:     "rgba(29,78,216,0.08)"

  # ── Dark mode ───────────────────────────────────────────────────
  dark-canvas:         "#07080A"              # Deepest base — cooler black
  dark-canvas-alt:     "#0C0D10"              # Stripe rows, zone demarcation
  dark-panel:          "#111318"              # Card, dialog — first step up
  dark-panel-raised:   "#181B22"              # Toolbar, elevated input areas
  dark-sidebar:        "#0C0D10"              # Left rail — matches canvas-alt
  dark-border:         "rgba(255,255,255,0.07)"   # Default edge
  dark-border-strong:  "rgba(255,255,255,0.13)"   # Focused, emphasized edge

  dark-text:           "#E8EAF0"        # Primary text — warm-cool white
  dark-text-secondary: "#9BA5BA"        # Supporting, secondary labels
  dark-text-muted:     "#5B6478"        # Placeholder, disabled, helper
  dark-text-on-accent: "#020617"        # Text on sky-blue accent fill

  dark-accent:         "#38BDF8"        # Sky blue — primary interactive signal
  dark-accent-hover:   "#7DD3FC"        # Hover: lightened sky
  dark-accent-subtle:  "rgba(56,189,248,0.10)"   # Wash for row hover / selected bg
  dark-accent-fg:      "#020617"        # Foreground on accent-fill buttons

  dark-success:        "#10B981"        # Emerald — saturated, readable on dark
  dark-success-subtle: "rgba(16,185,129,0.10)"
  dark-warning:        "#F59E0B"        # Amber — clear on dark
  dark-warning-subtle: "rgba(245,158,11,0.10)"
  dark-danger:         "#FB7185"        # Rose — visible on dark without harshness
  dark-danger-subtle:  "rgba(251,113,133,0.10)"
  dark-info:           "#38BDF8"        # Matches accent in dark
  dark-info-subtle:    "rgba(56,189,248,0.10)"

typography:

  page-title:
    fontFamily: "IBM Plex Sans"
    fontSize:   1.375rem
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: -0.015em

  section-title:
    fontFamily: "IBM Plex Sans"
    fontSize:   0.875rem
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: 0.005em

  body:
    fontFamily: "IBM Plex Sans"
    fontSize:   0.875rem
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: 0

  body-sm:
    fontFamily: "IBM Plex Sans"
    fontSize:   0.8125rem
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0

  control:
    fontFamily: "IBM Plex Sans"
    fontSize:   0.8125rem
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: 0

  label:
    fontFamily: "IBM Plex Sans"
    fontSize:   0.6875rem
    fontWeight: 700
    lineHeight: 1.35
    letterSpacing: 0.08em
    textTransform: uppercase

  mono-data:
    fontFamily: "JetBrains Mono"
    fontSize:   0.8125rem
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: 0

  mono-sm:
    fontFamily: "JetBrains Mono"
    fontSize:   0.75rem
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: 0

  metric:
    fontFamily: "JetBrains Mono"
    fontSize:   2.25rem
    fontWeight: 700
    lineHeight: 1
    letterSpacing: -0.025em

rounded:
  xs:   2px
  sm:   3px
  md:   5px
  lg:   7px
  xl:   10px
  full: 9999px

spacing:
  xxs:              2px
  xs:               4px
  sm:               8px
  md:               12px
  base:             16px
  lg:               24px
  xl:               32px
  xxl:              48px
  page-gutter:      24px
  content-max:      1440px
  topbar-height:    48px
  sidebar-width:    224px
  sidebar-collapsed: 56px
  control-height:   32px
  input-height:     34px
  row-height:       38px
  section-gap:      32px

components:

  # ── Buttons ──────────────────────────────────────────────────────
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor:       "{colors.accent-fg}"
    typography:      "{typography.control}"
    rounded:         "{rounded.md}"
    padding:         "5px 14px"
    height:          32px

  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"

  button-primary-active:
    backgroundColor: "{colors.accent-hover}"
    transform:       "scale(0.98)"

  button-secondary:
    backgroundColor: "{colors.panel-raised}"
    textColor:       "{colors.text}"
    typography:      "{typography.control}"
    rounded:         "{rounded.md}"
    padding:         "5px 14px"
    height:          32px
    border:          "1px solid {colors.border}"

  button-secondary-hover:
    backgroundColor: "{colors.canvas-alt}"
    borderColor:     "{colors.border-strong}"

  button-ghost:
    backgroundColor: "transparent"
    textColor:       "{colors.text-secondary}"
    typography:      "{typography.control}"
    rounded:         "{rounded.md}"
    padding:         "5px 10px"
    height:          32px

  button-ghost-hover:
    backgroundColor: "{colors.accent-subtle}"
    textColor:       "{colors.text}"

  button-danger:
    backgroundColor: "{colors.danger-subtle}"
    textColor:       "{colors.danger}"
    typography:      "{typography.control}"
    rounded:         "{rounded.md}"
    padding:         "5px 14px"
    height:          32px

  # ── Inputs & Controls ───────────────────────────────────────────
  input:
    backgroundColor: "{colors.panel}"
    textColor:       "{colors.text}"
    typography:      "{typography.body-sm}"
    rounded:         "{rounded.md}"
    padding:         "7px 12px"
    height:          34px
    border:          "1px solid {colors.border}"

  input-hover:
    borderColor: "{colors.border-strong}"

  input-focus:
    borderColor: "{colors.accent}"
    outline:     "2px solid {colors.accent-subtle}"

  input-placeholder:
    textColor: "{colors.text-muted}"

  toggle-on:
    backgroundColor: "{colors.accent}"
  toggle-off:
    backgroundColor: "{colors.border-strong}"

  # ── Table ───────────────────────────────────────────────────────
  table-header:
    backgroundColor: "{colors.canvas-alt}"
    textColor:       "{colors.text-muted}"
    typography:      "{typography.label}"
    height:          32px
    borderBottom:    "1px solid {colors.border}"

  table-row:
    backgroundColor: "{colors.panel}"
    textColor:       "{colors.text}"
    height:          38px
    borderBottom:    "1px solid {colors.border}"

  table-row-stripe:
    backgroundColor: "{colors.canvas-alt}"

  table-row-hover:
    backgroundColor: "{colors.accent-subtle}"

  table-row-selected:
    backgroundColor: "{colors.accent-subtle}"
    borderLeft:      "2px solid {colors.accent}"

  # ── Badges / Status Pills ────────────────────────────────────────
  badge-success:
    backgroundColor: "{colors.success-subtle}"
    textColor:       "{colors.success}"
    typography:      "{typography.label}"
    rounded:         "{rounded.sm}"
    padding:         "2px 8px"

  badge-danger:
    backgroundColor: "{colors.danger-subtle}"
    textColor:       "{colors.danger}"
    typography:      "{typography.label}"
    rounded:         "{rounded.sm}"
    padding:         "2px 8px"

  badge-warning:
    backgroundColor: "{colors.warning-subtle}"
    textColor:       "{colors.warning}"
    typography:      "{typography.label}"
    rounded:         "{rounded.sm}"
    padding:         "2px 8px"

  badge-info:
    backgroundColor: "{colors.info-subtle}"
    textColor:       "{colors.info}"
    typography:      "{typography.label}"
    rounded:         "{rounded.sm}"
    padding:         "2px 8px"

  badge-neutral:
    backgroundColor: "{colors.canvas-alt}"
    textColor:       "{colors.text-secondary}"
    typography:      "{typography.label}"
    rounded:         "{rounded.sm}"
    padding:         "2px 8px"

  # ── Status Dot ──────────────────────────────────────────────────
  status-dot:
    size:   6px
    rounded: "{rounded.full}"
  status-dot-success: { color: "{colors.success}" }
  status-dot-running: { color: "{colors.info}" }
  status-dot-warning: { color: "{colors.warning}" }
  status-dot-failed:  { color: "{colors.danger}" }
  status-dot-idle:    { color: "{colors.text-muted}" }

  # ── Navigation ──────────────────────────────────────────────────
  nav-item:
    backgroundColor: "transparent"
    textColor:       "{colors.text-secondary}"
    typography:      "{typography.body-sm}"
    rounded:         "{rounded.md}"
    padding:         "6px 10px"
    height:          32px

  nav-item-hover:
    backgroundColor: "{colors.accent-subtle}"
    textColor:       "{colors.text}"

  nav-item-active:
    backgroundColor: "{colors.accent-subtle}"
    textColor:       "{colors.text}"
    fontWeight:      600
    borderLeft:      "2px solid {colors.accent}"

  nav-group-label:
    textColor:   "{colors.text-muted}"
    typography:  "{typography.label}"
    paddingLeft: "10px"
    marginTop:   "20px"
    marginBottom: "4px"

  # ── Cards & Panels ──────────────────────────────────────────────
  card:
    backgroundColor: "{colors.panel}"
    rounded:         "{rounded.lg}"
    border:          "1px solid {colors.border}"
    padding:         "20px"

  card-header:
    backgroundColor: "{colors.canvas-alt}"
    borderBottom:    "1px solid {colors.border}"
    padding:         "10px 16px"

  metric-card:
    backgroundColor: "{colors.panel}"
    rounded:         "{rounded.lg}"
    border:          "1px solid {colors.border}"
    padding:         "16px 20px"

  # ── Topbar ──────────────────────────────────────────────────────
  topbar:
    backgroundColor: "{colors.panel}"
    height:          48px
    borderBottom:    "1px solid {colors.border}"
    padding:         "0 24px"

  # ── Sidebar ─────────────────────────────────────────────────────
  sidebar:
    backgroundColor: "{colors.sidebar}"
    width:           224px
    borderRight:     "1px solid {colors.border}"
    padding:         "16px 8px"

  # ── Toolbar ─────────────────────────────────────────────────────
  toolbar:
    backgroundColor: "{colors.canvas-alt}"
    borderBottom:    "1px solid {colors.border}"
    height:          38px
    padding:         "0 12px"

shadows:
  xs: "0 1px 2px rgba(10,11,14,0.04)"
  sm: "0 2px 6px rgba(10,11,14,0.06), 0 1px 2px rgba(10,11,14,0.04)"
  md: "0 4px 12px rgba(10,11,14,0.08), 0 2px 4px rgba(10,11,14,0.04)"
  note: >
    No glow shadows. No colored elevation. No accent-tinted drop shadows.
    Elevation is always expressed in surface color steps + border containment.
    Maximum opacity: 0.08. Shadows are structural anchors, not decoration.

---

## Overview

CrawlerAI Console is an operator-first data workspace: dense, precise, and
undecorated. Its visual language is derived from three reference systems:

**Linear** supplies the dark-mode DNA — near-black canvas, cool-neutral text,
luminance-stepped surfaces, and a single precisely-placed accent color. Every
pixel earns its place; decoration is disqualified by default.

**Vercel** supplies the black-and-white discipline — confident near-black
primary buttons, hairline borders, and the conviction that negative space is
a feature, not a failure.

**IBM Carbon** supplies the grid rigor — 8px unit spacing, sticky table headers,
functional label formatting, and the enterprise-grade structural clarity
required by a tool processing thousands of crawl records.

The result is a workspace where crawl operators can watch runs, scan extractions,
compare selector output, and diagnose failures at a glance — without the visual
noise of a dashboard optimized for demos rather than daily use.

---

## Colors

### Light Mode — Cool Graphite

Light mode is not warm parchment. It is a cool, clean slate: `#F7F8FA` canvas
with the faintest blue-grey cast. This distinguishes the UI from generic white
apps and signals that the tool belongs in a developer's environment rather than
a marketing SaaS.

**Accent is deep slate navy (`#0F172A`).** Primary buttons are confident and dark.
This is not a playful brand accent — it is the on/off signal of an industrial control.

Use the accent for: primary buttons, active navigation, focus rings, selected row
indicators, and run state markers. Nowhere else.

Semantic colors carry literal meaning. `success (#047857)` means a crawl
completed cleanly. `danger (#BE123C)` means a block or failure. `warning (#92400E)`
means degraded throughput or a soft error. `info (#1D4ED8)` means a run is in
progress. Do not repurpose semantic colors for decoration.

### Dark Mode — Obsidian Console

Dark mode is a deep, cool black: `#07080A`. This is darker and cooler than the
previous `#0C0D0E`, increasing perceived depth and reinforcing the terminal
aesthetic.

**Accent is sky blue (`#38BDF8`).** This is a deliberate departure from
indigo-violet. Sky blue evokes networks, data pipelines, and web infrastructure
without feeling artificial or consumer-playful. It provides a clear interactive
signal with high legibility on the deep-black canvas.

Use the sky-blue accent for: interactive highlights, active states, running
indicators, focus rings, selected rows, and progress fills. Nowhere else.

Surfaces use luminance stepping: `canvas (07080A)` → `panel (111318)` →
`panel-raised (181B22)`. This stepping is the primary depth signal. Borders
(`rgba(255,255,255,0.07)`) are hairline whispers, not structural walls.

### Semantic Color Rules

- **Success** = crawl completed, record saved, selector resolved
- **Danger** = crawl failed, bot block, extraction error, critical threshold
- **Warning** = degraded mode, fallback triggered, slow response, soft limit
- **Info** = run in progress, loading, pending job
- Status must always include text. Color is a redundancy layer, not the primary signal.

---

## Typography

Two typefaces. No exceptions.

**IBM Plex Sans** handles all UI text: navigation, labels, body copy, controls,
headings, and status messages. It is technical enough to read as a developer
tool but warmer than Inter, making long sessions less fatiguing. Weights: 400
(body), 600 (controls and nav), 700 (section titles and page titles).

**JetBrains Mono** handles all data: run IDs, timestamps, URLs, domain names,
log output, JSON, record counts, metric values, table body cells containing
identifiers or numbers. Any value that must align vertically or scan as a unit
gets monospace treatment.

### Type Scale Rationale

- **Page Title** (`1.375rem / 700 / -0.015em`): Tight tracking at heading size
  prevents loose, marketing-page feeling. This is a tool; headings are orientation
  markers, not announcements.
- **Section Title** (`0.875rem / 700 / 0.005em`): Same size as body but 700
  weight creates clear hierarchy without size jumps. Slightly positive tracking
  keeps it readable at small size.
- **Label** (`0.6875rem / 700 / 0.08em uppercase`): Uppercase column headers and
  section eyebrows. 0.08em tracking is mandatory — without it, uppercase at
  11px is unreadable.
- **Metric** (`2.25rem / JetBrains Mono 700 / -0.025em`): KPI numbers like total
  runs, record counts. Tight tracking on a large mono number eliminates the
  loose, calculator-display feeling.
- **Control** (`0.8125rem / 600`): Button labels, dropdown text, tab labels.
  Weight 600 differentiates them from body text without uppercase.
- **Mono Data** (`0.8125rem / JetBrains Mono 400`): Table cells containing URLs,
  IDs, counts. Must align vertically; regular weight keeps density readable.

### Typography Rules

- Use positive letter-spacing only for uppercase label text. All other text: 0 or
  slightly negative tracking on display sizes.
- Do not use italic in UI. Italic is reserved for prose within log/result content
  only if the data itself contains it.
- Do not scale monospace metrics text in marketing ways. A count of `69` in a
  KPI card should not be massive; `2.25rem` is the ceiling.

---

## Spacing & Layout

### Grid

All spacing derives from an **8px base unit**. Half-steps (4px) are permitted for
tight component internals only: icon-to-label gaps, status dot spacing, badge
horizontal padding. Quarter-steps (2px) are allowed only for border-radius offsets
and micro-adjustments.

### Shell

```
Topbar:    48px height, full-width, sticky
Sidebar:   224px width (collapsed: 56px), fixed left
Canvas:    flex-1, max-width 1440px content with 24px page gutter on both sides
```

The sidebar and topbar define the operator shell. They never scroll. All content
is in the main canvas.

### Page Anatomy

Prefer these layouts (in order of priority):

1. **Full-width table** with sticky column headers, filter toolbar above, pagination below
2. **Split pane**: config/form left (40%) + live preview or result right (60%)
3. **Two-column detail**: form fields left, context panel right
4. **Metric row + table** (dashboard): KPI strip at top spanning full width, table below

Do not create dashboard mosaics with 4+ card grids. Do not use hero sections. Do
not use full-bleed imagery. Do not use decorative dividers.

### Spacing Application

- Component internal padding: 8px vertical / 12px horizontal (inputs, buttons)
- Table row height: 38px
- Table header height: 32px
- Section gap (between major page sections): 32px
- Card padding: 20px
- Toolbar height: 38px (single row of controls)
- Nav item height: 32px

---

## Components

### Buttons

Three tiers:

**Primary** — dark slate fill (`#0F172A` light / `#38BDF8` dark), 32px height,
5px radius. Used once per major context. This is the "do the thing" button:
Start Crawl, Save to Memory, Export. Not every panel needs one.

**Secondary** — panel-raised fill with 1px border. Same height and radius as
primary. Used for supporting actions: Reset, Cancel, Download, Copy. Multiple
secondary buttons per panel are acceptable.

**Ghost** — transparent fill, text-secondary color. Used inside toolbars, filter
rows, and table actions. Compact horizontal padding (10px). Never use for
destructive actions.

**Danger** — danger-subtle fill with danger text. Used for Delete, Clear History,
Reset Workspace. Always placed last in action groups with visible separation from
non-destructive actions.

Button rules:
- No glow shadows on any button state
- Active/pressed: `scale(0.98)` transform, 80ms duration
- Height is always 32px. Do not use tall "hero" buttons inside the app shell
- Never use accent-color fill for secondary or ghost buttons

### Inputs

Single-line inputs: 34px height, `{rounded.md}` (5px), `border: 1px solid border`,
fill is `{colors.panel}`. On focus: border swaps to accent color + 2px outline
using `accent-subtle` fill for the glow ring. No shadow on focus — the color
change is sufficient.

Textarea: same border/radius treatment, min-height 80px, mono font if it accepts
URL or JSON input.

Toggle: pill-shaped, 32×18px, accent-fill when ON, border-strong when OFF.
No iOS-style shadows.

### Tables

Tables are the core component of this system. Everything else supports them.

**Header row**: `{colors.canvas-alt}` fill, `{typography.label}` text (uppercase
0.08em tracking), 32px height, sticky on scroll. Sort arrows appear on hover.

**Body rows**: 38px height, alternating `panel` / `canvas-alt` stripe. Row hover
applies `accent-subtle` wash. Selected row applies `accent-subtle` fill +
`2px solid accent` left border edge.

**URL / domain cells**: Always `mono-data` type. Truncate with ellipsis at column
width; full value on hover tooltip.

**Status cells**: Status dot (6px circle, `{rounded.full}`) + badge text side by
side. Never status color alone.

**Action cells**: Ghost button(s), icon-only if space is tight, appear on row hover.

**Column header text is always uppercase `label` type.** Body cell text is
`body-sm` for strings and `mono-data` for IDs, URLs, counts, and codes.

### Badges

Compact, not pill-heavy. Use `{rounded.sm}` (3px) not `{rounded.full}`. Each badge
contains a status dot + text. Width is content-driven — do not force fixed widths.

Badge color maps: success = emerald, danger = rose, warning = amber, info = blue,
neutral = grey. All use `subtle` background fills at ~8–10% opacity.

Badge text is always `{typography.label}` (uppercase, 0.08em tracking, 11px).

### Navigation

Left sidebar uses two-tier nav: group labels (uppercase `label` style, muted color)
followed by nav items (32px height, 5px radius).

Active nav item: `accent-subtle` fill, 600 font weight, `2px solid accent` left
border. The left border is 2px and flush with the sidebar inner edge (not inset).

Nav group labels have `20px` margin-top and `4px` margin-bottom. They are
orientation markers, not clickable elements.

Sidebar footer: user avatar + name, positioned absolutely at bottom left. No action
buttons in the sidebar footer — overflow menu on the avatar only.

### KPI / Metric Cards

Four-across strip at dashboard top. Each card: 20px padding, 1px border,
`{rounded.lg}` (7px). Internal layout: `{typography.label}` heading above,
`{typography.metric}` (JetBrains Mono 700, 2.25rem) value below.

Do not add sparklines, trend arrows, or change indicators inside metric cards unless
they are interactive and reflect real data. Decorative micro-charts are not allowed.

### Status Indicators

The platform has five run states. Map them consistently everywhere:

| State     | Dot color     | Badge   | Text          |
|-----------|---------------|---------|---------------|
| Completed | success       | success | Completed     |
| Running   | info          | info    | Running       |
| Queued    | neutral/muted | neutral | Queued        |
| Failed    | danger        | danger  | Failed        |
| Blocked   | warning       | warning | Blocked       |

State must always be communicated in text, not color alone.

---

## Motion

Motion is functional. It communicates state change, not personality.

**Easing:**
- `ease-out: cubic-bezier(0.0, 0.0, 0.2, 1)` — Elements entering the screen
- `ease-in-out: cubic-bezier(0.4, 0.0, 0.2, 1)` — State transitions
- `ease-in: cubic-bezier(0.4, 0.0, 1, 1)` — Elements leaving the screen

**Duration:**
- Micro (hover, focus ring, button active): **80–120ms**
- Transition (dropdown open, tab switch, row selection): **150ms**
- Panel (sidebar expand/collapse, modal enter): **180–220ms**

**Properties allowed:** `background-color`, `color`, `border-color`, `opacity`,
`transform` (scale only, never translate-y for hover float effects).

**Properties not allowed:** box-shadow transitions (flicker on some GPUs),
filter transitions, width/height transitions.

**No bounce easing.** No spring physics. No hover float (`translateY`). Pressed
state only: `scale(0.98)` at 80ms ease-in.

Status indicator dots for running jobs may use a slow `pulse` animation
(`opacity: 1 → 0.4 → 1`, 2s duration, infinite). This is the only decorative
motion in the system.

---

## Voice & Tone

CrawlerAI is a tool for operators who are watching data pipelines. The UI copy
should reflect that:

**Be literal.** Label buttons with the verb and noun of exactly what happens:
"Start Crawl", "Save to Memory", "Export Records", "Clear Run History". Not
"Go", "Confirm", "OK".

**Use operator vocabulary.** "Run", "Crawl", "Record", "Surface", "Domain",
"Selector", "Field", "LLM", "Proxy", "Block". Do not soften technical terms
into consumer language.

**Keep error messages precise.** "Bot block detected on rockler.com. Try enabling
Proxy List or switching to Browser mode." Not "Something went wrong. Please try
again." Give the operator enough information to act.

**Section headers are uppercase `label` style** — they are category dividers,
not prose headings. Write them as noun phrases: "TARGET URL", "FIELD
CONFIGURATION", "CRAWL SETTINGS", "ADVANCED SETTINGS".

**Empty states** contain two lines max: a state description + a single action
call. "No selector rows yet. Generate fields from the target URL." No
motivational copy, no decorative illustrations.

---

## Brand Identity

CrawlerAI is an internal data tool, not a consumer product. Its brand identity
is expressed entirely through precision and restraint — not logos, gradients, or
personality mascots.

**Wordmark:** "CrawlerAI" set in IBM Plex Sans 700. No special treatment, no
custom letterform, no icon lock-up required. The wordmark in the sidebar header
is the only brand expression.

**Logo mark:** The square `[C]` icon in the topbar. Solid fill, `{rounded.sm}`
(3px radius), `{colors.text}` on light / `{colors.dark-text}` on dark. This
icon can be displayed alone in collapsed sidebar mode.

**Identity signals:** Precision in data formatting, monospace type on all
records, consistent status semantics, and the restraint to omit anything that
doesn't serve the operator.

---

## Anti-Patterns

These are disqualifying. Any agent or developer reading this document must not
produce output containing any of the following:

### Color Anti-Patterns

- ❌ Gradient fills on any interactive element, surface, or background band
- ❌ Radial gradients used as ambient background lighting
- ❌ Orange, amber, or warm accent colors for interactive elements
- ❌ Colored box-shadow "glow" on buttons or cards
- ❌ Accent-tinted elevation shadows
- ❌ Using semantic colors (success, danger, warning) as decoration
- ❌ Mixing warm and cool surface tones in the same mode
- ❌ Semi-transparent accent fills on non-interactive structural elements

### Typography Anti-Patterns

- ❌ Negative letter-spacing on labels or uppercase text
- ❌ Italic type in UI navigation or table content
- ❌ All-caps section bodies (only headers use uppercase label style)
- ❌ Displaying monospace metric values at sizes above `2.25rem`
- ❌ Using sans-serif for URLs, record counts, IDs, or timestamps
- ❌ Mixed font families beyond IBM Plex Sans + JetBrains Mono

### Layout Anti-Patterns

- ❌ Hero sections inside the app shell
- ❌ Marketing banners or promotional callout cards
- ❌ Dashboard card mosaics (4+ equal-weight cards in a grid)
- ❌ Nested cards (card inside card)
- ❌ Full-bleed imagery or illustration panels
- ❌ Content wider than 1440px or without 24px page gutter
- ❌ Scroll-jacking or parallax effects

### Motion Anti-Patterns

- ❌ `translateY` hover float effects on buttons or cards
- ❌ Bounce or spring easing
- ❌ box-shadow transitions
- ❌ Decorative entrance animations on table rows
- ❌ Animation duration above 220ms for component-level transitions
- ❌ Multiple pulsing elements simultaneously (max one pulse indicator per viewport)

### Component Anti-Patterns

- ❌ Pill-heavy badges with `{rounded.full}` (use `{rounded.sm}` instead)
- ❌ Buttons taller than 32px inside the app shell
- ❌ Accent-colored secondary or ghost buttons
- ❌ Status communicated by color alone (must include text)
- ❌ Table rows shorter than 38px or taller than 44px
- ❌ KPI cards with decorative sparklines or trend arrows on placeholder data
- ❌ More than one primary button visible per panel at the same time

### The Root Rule

> **If it would look at home in a SaaS marketing landing page, it does not
> belong inside the CrawlerAI operator console.**