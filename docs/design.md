---
version: "1.2"
name: "Invoro Refresh Console"
description: >
  Operator-first crawler workspace using the Invoro Refresh visual system:
  compact professional controls, quiet light surfaces, Feedonomics-style blue
  accent, and preserved dark theme colors. This spec changes visual treatment
  only; it does not change page structure, feature behavior, or font families.
colors:
  light-canvas: "#fafbfc"
  light-alt: "#f4f6f9"
  light-surface: "#ffffff"
  light-sidebar: "#fbfcfd"
  light-sunken: "#f7f8fa"
  light-border: "#e7ebef"
  light-border-strong: "#d5dae1"
  light-border-subtle: "#eef1f4"
  light-divider: "#edf0f3"
  light-text-primary: "#0a1220"
  light-text-secondary: "#3d475a"
  light-text-muted: "#6b7487"
  light-text-faint: "#98a0b0"
  light-accent: "#1f6fd6"
  light-accent-hover: "#195fb8"
  light-accent-soft: "rgba(31,111,214,.1)"
  light-accent-soft-2: "rgba(31,111,214,.05)"
  light-accent-border: "rgba(31,111,214,.28)"

  dark-canvas: "#09090b"
  dark-alt: "#121214"
  dark-panel: "#18181b"
  dark-elevated: "#242427"
  dark-border: "#27272a"
  dark-border-strong: "#3f3f46"
  dark-text-primary: "#f4f4f5"
  dark-text-secondary: "#a1a1aa"
  dark-text-muted: "#a1a1aa"
  dark-accent: "#4c84c8"
  dark-accent-hover: "#76a6df"

typography:
  font-policy: "Do not change families. Use current app sans and mono tokens."
  display:
    fontSize: "28px"
    fontWeight: "650"
    lineHeight: "1"
    letterSpacing: "-0.03em"
  page-title:
    fontSize: "28px"
    fontWeight: "650"
    lineHeight: "1.1"
    letterSpacing: "-0.02em"
  section-title:
    fontSize: "18px"
    fontWeight: "600"
    lineHeight: "1.25"
    letterSpacing: "-0.01em"
  body:
    fontSize: "14px"
    fontWeight: "400"
    lineHeight: "1.5"
  body-sm:
    fontSize: "13px"
    fontWeight: "400"
    lineHeight: "1.45"
  label:
    fontSize: "11px"
    fontWeight: "600"
    lineHeight: "1.4"
    letterSpacing: "0.06em"

spacing:
  base: "4px"
  control-height: "32px"
  control-height-sm: "26px"
  control-height-lg: "36px"
  page-gutter: "32px desktop, 24px compact, 16px mobile"
  section-gap: "20px"
  card-padding: "18px"
  table-header-height: "40px"
  table-row-height: "44px"

rounded:
  xs: "3px"
  sm: "5px"
  md: "7px"
  lg: "10px"
  xl: "14px"
  "2xl": "20px"
  full: "9999px"

components:
  buttons:
    primary: "filled accent, white text, 32px height, 7px radius, medium weight"
    secondary: "surface background, strong border, subtle shadow"
    ghost: "transparent, muted text, neutral hover wash"
    destructive: "surface background with danger text and danger border"
  tabs:
    segmented: "sunken surface with 2px padding, active item on surface with 1px border"
    underline: "divider baseline with 2px accent indicator on active tab"
  cards:
    default: "surface background, 1px border, 10px radius, subtle shadow only when raised"
  tables:
    header: "sunken background, 10px-11px uppercase labels, sticky when table scrolls"
    rows: "44px rhythm, divider lines, subtle sunken hover background"
  metrics:
    label: "11px uppercase muted label"
    value: "tabular numeric display, 28px, weight 650"
---

# Overview

Invoro uses a compact operator console style. The visual goal is professional density: clear hierarchy, predictable controls, and quiet data surfaces. This migration adopts the Invoro Refresh reference from `C:\Users\abhij\Downloads\CrawlerAI` while preserving existing application behavior and page arrangement.

The app keeps its current font-family tokens. Only size, weight, color, hierarchy, spacing, component treatment, and light-theme palette change.

# Color System

Light mode uses a cool off-white canvas (`#fafbfc`), white surfaces, subtle gray borders, and one primary blue accent (`#1f6fd6`). Accent should appear on primary actions, active navigation, focused controls, selected tabs, progress, and key status emphasis.

Dark mode colors are intentionally preserved from the current app. Do not retune dark surfaces, dark borders, dark text, or dark accent during this visual migration.

# Typography

Use the existing sans token for product UI and the existing mono token for technical values. Do not introduce or import a new font family.

Headings use tighter line height and medium-to-semibold weights. Body text stays compact at 13px-14px for dense operator screens. Numeric values, run IDs, URLs, logs, code, and tabular metrics use tabular figures and the mono token where the existing component already treats them as technical data.

# Layout

Spacing follows a 4px grid with a denser control rhythm:

- Default controls: 32px high.
- Small controls: 26px high.
- Large controls: 36px high.
- Table rows: 44px.
- Table headers: 40px.
- Page content max width remains 1440px.
- Existing page layout and element order must not change.

# Components

Buttons, inputs, tabs, cards, metrics, and tables should inherit from shared primitives first. Page-level hardcoded styling should be removed when a shared primitive can own it.

Cards and panels use borders and subtle shadows instead of heavy gradients. Tables use sticky, quiet headers and a soft hover wash. Tabs use either segmented controls or underline tabs from the shared `TabBar` primitive.

# Migration Rules

- No feature changes.
- No page arrangement changes.
- No font family changes.
- Do not change dark theme color values.
- Replace hardcoded visual values with tokens where practical.
- Keep dynamic inline styles only for true runtime values such as progress width, virtualized spacer height, and measured tooltip positions.
