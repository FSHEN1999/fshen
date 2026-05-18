---
version: alpha
name: DPU-testing-toolkit-design-system
description: A practical design system for the HSBC DPU testing toolkit. It turns the useful parts of awesome-design-md into local guidance for AI agents: dense operational screens, clear workflow status, restrained financial-tool styling, and documentation-friendly layouts. The system is intentionally not a copy of any public brand. It blends engineering-tool precision, documentation readability, and DPU workflow semantics.
---

# DPU DESIGN.md

Use this file when changing any DPU-facing UI, internal dashboard, mock service page, report page, or generated HTML document in this repository.

This design system is for operational testing tools, not marketing pages. Prioritize speed, scanability, state clarity, and safe execution over decoration.

## Visual Theme & Atmosphere

- Quiet financial-operations UI: professional, compact, and readable.
- The interface should feel like a control console for test execution, webhook simulation, DB verification, and environment switching.
- Use restrained color with one clear action accent and explicit status colors.
- Prefer dense but organized information. Avoid oversized hero marketing layouts, decorative cards, and single-hue palettes.
- Use real workflow language: environment, phone, session, application, merchant, PSP, eSign, drawdown, repayment, log, report.

## Color Palette & Roles

| Token | Hex | Role |
|---|---:|---|
| `canvas` | `#f5f8fb` | App background |
| `canvas-dark` | `#08121c` | Dark mode background |
| `surface` | `#ffffff` | Primary panel surface |
| `surface-soft` | `#eef3f7` | Secondary panel or table header |
| `surface-dark` | `#111c2a` | Dark mode panel |
| `ink` | `#152033` | Primary text |
| `ink-muted` | `#5d6b82` | Secondary text |
| `ink-soft` | `#8a99ab` | Tertiary text and metadata |
| `line` | `#d9e2ec` | Borders and dividers |
| `line-dark` | `#2a3a4d` | Dark mode borders |
| `primary` | `#00684a` | Primary action and active state |
| `primary-hover` | `#05825f` | Hover or active action |
| `primary-soft` | `#dff4ec` | Low-emphasis primary surface |
| `secondary` | `#0d5dd3` | Links, AI actions, secondary command |
| `warning` | `#b7791f` | Pending, processing, attention |
| `success` | `#14804a` | Success, connected, approved |
| `error` | `#c0392b` | Error, rejected, failed |
| `info` | `#0d6b8f` | Neutral system information |

## Typography Rules

Use system fonts only unless a local app already ships a font.

| Token | Font | Size | Weight | Line Height | Usage |
|---|---|---:|---:|---:|---|
| `display` | Segoe UI, PingFang SC, Microsoft YaHei, sans-serif | 40-56px | 700 | 1.08 | App shell headline only |
| `page-title` | same | 26-32px | 700 | 1.2 | View titles |
| `section-title` | same | 18-22px | 700 | 1.3 | Card headers and form groups |
| `body` | same | 14-16px | 400 | 1.55 | Forms, descriptions, normal text |
| `label` | same | 13-14px | 600 | 1.35 | Field labels and metadata |
| `caption` | same | 12px | 500 | 1.4 | Timestamps, badges, table hints |
| `mono` | Cascadia Code, Consolas, ui-monospace, monospace | 12-13px | 400 | 1.55 | JSON, SQL, logs, ids |

Do not use oversized display text inside cards, sidebars, tables, logs, or controls.

## Spacing, Radius, And Elevation

| Token | Value | Usage |
|---|---:|---|
| `space-xs` | 4px | Icon gaps, dense metadata |
| `space-sm` | 8px | Compact control gaps |
| `space-md` | 12px | Form row gaps |
| `space-lg` | 16px | Card internal rhythm |
| `space-xl` | 24px | Main panel padding |
| `space-2xl` | 32px | Page-level spacing |

| Token | Value | Usage |
|---|---:|---|
| `radius-sm` | 6px | Inputs, small controls |
| `radius-md` | 8px | Buttons, chips |
| `radius-lg` | 12px | Repeated cards |
| `radius-xl` | 16px | Primary panels |
| `radius-pill` | 999px | Status pills and icon-only rounded controls |

Use soft elevation only for the top-level shell or important panels. Repeated operational cards should mostly rely on borders and surface contrast.

## Component Guidance

### App Shell

- Use a constrained shell width around `min(1520px, calc(100% - 32px))`.
- Major tool screens should use a two-column desktop layout when there is a primary operation area plus session/log side panel.
- Collapse to one column below tablet width.

### Header / Hero Band

- Use a compact operational hero, not a landing-page hero.
- The first viewport should immediately expose the main work surface below the header.
- Header content should show what the tool does and current system state, not marketing copy.

### Cards And Panels

- Use cards for bounded tools, repeated operations, logs, activity items, and modal/drawer surfaces.
- Avoid card-in-card nesting unless the inner card is a log row, form block, or repeated operation item.
- Prefer 12-16px radius for operational panels. Avoid 24px+ radius except for an existing app shell that already uses it.

### Forms

- Labels should be short and concrete.
- Use selects for fixed workflow states and failure reasons.
- Keep environment, phone number, journey, currency, and status controls visible near the action they affect.
- Buttons that trigger irreversible or state-changing operations must be visually distinct from navigation or refresh actions.

### Status And Badges

- Use color semantically:
  - success: `APPROVED`, `SUCCESS`, connected, completed
  - warning: `PROCESSING`, `PENDING`, running
  - error: `REJECTED`, `FAIL`, disconnected, exception
  - info: environment, session, neutral state
- Do not encode status by color alone; include text labels.

### Logs, JSON, SQL, And IDs

- Render logs and payloads in monospace.
- Preserve line breaks and wrap long text safely.
- Long IDs should be selectable and break across lines without expanding the layout.
- Prefer a dark log strip only when it improves contrast for payload reading.

### AI Assistant Surfaces

- AI chat or analysis panels should be secondary, usually a drawer or side panel.
- AI output should never obscure the active operation form.
- Include execution environment context when AI actions can affect SIT/UAT/REG/DEV.

## Responsive Behavior

| Width | Behavior |
|---:|---|
| `< 768px` | Single-column layout, full-width forms, drawers become full width |
| `768-1100px` | Two-column where useful, but keep side panels below main forms if content becomes cramped |
| `> 1100px` | Main operation column plus session/log side column |

Touch targets should be at least 40px high for primary actions and inputs.

## Do's

- Keep business-state transitions visible and auditable.
- Put environment and session context close to action buttons.
- Use compact grids, tables, accordions, and side panels for repeated workflow operations.
- Prefer clear operational labels over generic UI copy.
- Keep generated reports and docs readable when pasted into MeterSphere, PRs, or release notes.
- When borrowing from `awesome-design-md`, borrow structure and token discipline, not brand identity.

## Don'ts

- Do not copy a public brand's exact visual identity into DPU tools.
- Do not make internal DPU tools look like a marketing landing page.
- Do not hide critical fields such as env, phone, amount, status, or failure reason behind decorative layout.
- Do not use decorative gradients, bokeh, or one-note color themes as the main visual language.
- Do not rely on "clicked" or "sent" as success language unless downstream state or response detail is visible.

## Agent Prompt Guide

When asking an AI agent to change DPU UI, use this pattern:

```text
Read DESIGN.md first. Build this as a DPU operational testing interface:
- dense, scan-friendly layout
- explicit environment/session/status context
- restrained financial-tool visual style
- logs and payloads readable in monospace
- no marketing hero or decorative card-heavy layout
```

For `mockapi/frontend`, also read `mockapi/frontend/DESIGN.md`.

