---
version: "4.1"
name: "Invoro Design System v4.1"
description: >
  CrawlerAI v4 refined-minimal operator design system adapted to Invoro's
  Next.js shell, with local Switzer body, Satoshi display, and Geist Mono.
fonts:
  body: "Switzer Variable"
  display: "Satoshi Variable"
  mono: "Geist Mono"
themes:
  light:
    background-base: "#fafafa"
    background-alt: "#f4f4f5"
    background-panel: "#ffffff"
    background-well: "#ececef"
    text-primary: "#18181b"
    accent: "#5e6ad2"
  dark:
    background-base: "#0e0f12"
    background-alt: "#131418"
    background-panel: "#16171c"
    background-well: "#22242b"
    text-primary: "#ececf1"
    accent: "#5e6ad2"
geometry:
  sidebar-expanded: "232px"
  sidebar-collapsed: "58px"
  topbar: "48px"
  content-max: "1440px"
  content-gutter: "24px; 16px below 480px"
  controls: "28px / 32px / 36px"
  table-header: "30px"
  table-row: "38px"
---

# Invoro Design System v4.1

`frontend/app/globals.css` is the canonical token and global-style source. This document records its intended use. CrawlerAI v4 is the visual authority; Invoro keeps its Next.js routing, product workflows, copy, and API contracts.

## Visual Language

Use a compact, refined operator interface:

- Neutral flat surfaces with shallow, ambient depth.
- Indigo accent for selection, focus, and primary actions.
- Semantic success, warning, danger, and information tokens for state.
- Dense analytical tables and controls on a strict 4px grid.
- Statuses use a dot plus text. Neutral identifiers may use a subtle chip.
- Motion stays within the shared 100ms, 180ms, and 280ms timings.

Do not introduce raw page-level colors, decorative gradients, glass effects, oversized radii, or parallel token systems.

## Typography

- Switzer is the body and interface face. Normal and italic variable files cover weights 100–900.
- Satoshi is the display and heading face. Normal and italic variable files cover weights 300–900.
- Geist Mono is retained for code, URLs, identifiers, logs, and tabular technical values.

Invoro uses a 14px operator baseline, adapted from [SAP Fiori's ERP typography guidance](https://experience.sap.com/fiori-design-web/typography/). Fiori uses 14px medium text for buttons, inputs, tables, and trees; 12px small text is exceptional supporting information. Invoro preserves that density model while keeping its established font families.

| Role       | Size | Use                                             |
| ---------- | ---: | ----------------------------------------------- |
| Caption    | 12px | Metadata, timestamps, terse technical labels    |
| Body       | 14px | Default UI, controls, prose, tables, navigation |
| Body large | 16px | Emphasized body and dialog titles               |
| Section    | 18px | Card and section headings                       |
| Subpage    | 20px | Nested page headings                            |
| Page       | 24px | Page and authentication headings                |
| Display    | 32px | KPIs and display values                         |

`frontend/app/globals.css` is the only size source. Its `--type-scale-*` tokens feed semantic role classes, table and activity tokens, chart labels, and Tailwind `text-*` compatibility aliases. Screens must not introduce raw pixel font sizes. Use display typography for headings, body typography for controls and prose, and mono only when content is technical or numeric.

## Tokens And Themes

Tailwind v4 utilities consume semantic variables through the `@theme inline` bridge. Prefer names such as `bg-panel`, `text-secondary`, `border-border`, `text-accent-text`, and `shadow-card`. Do not use arbitrary `var(--token)` escapes in class strings.

Light and dark themes share semantic roles. `public/theme-init.js` applies the stored theme before paint. Both themes must retain visible focus, reduced-motion, forced-colors, and print behavior.

## Shell

The operator shell uses:

- 232px expanded and 58px collapsed sidebar.
- 48px top bar.
- 1440px centered content maximum.
- 24px normal content gutter and 16px narrow-mobile gutter.

The shell keeps Invoro navigation, authentication, notifications, reset actions, and Next.js links. Responsive collapse must hydrate deterministically and preserve the explicit stored preference.

## Shared Components

Use the focused owners under `frontend/components/ui`:

- Buttons: semantic CVA variants and 28/32/36px sizes.
- Cards: base and compound header/content/footer slots.
- Inputs and fields: explicit labels, descriptions, errors, focus, and disabled states.
- Badges: dot-and-text semantic states.
- Dialogs and drawers: Radix focus and dismissal behavior.
- Tables: 30px sticky headers, 38px rows, tabular numeric alignment.
- Dropdowns, toggles, tooltips, and skeletons: shared accessible interactions.
- Page patterns: focused modules re-exported through `patterns.tsx`.

Barrels are compatibility entry points only. Implementation belongs in focused owner files. Feature modules keep API calls and product behavior in their existing subsystem.

## Accessibility And Motion

- Focus uses the shared visible outline/ring.
- Body and placeholder contrast must meet WCAG AA.
- Reduced-motion collapses animations and transitions to 1ms.
- Forced-colors provides explicit outlines and borders.
- Interactive nesting is invalid; one control must not contain another.
- Every field, toggle, icon button, and combobox needs an accessible name.

Use only shared shimmer, fade, dropdown, and spin motion unless a product interaction demonstrates another need.
