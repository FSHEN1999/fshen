---
version: alpha
name: DPU-mockapi-frontend-design-system
description: Frontend-specific design guidance for the DPU Mock API console. This adapts the useful DESIGN.md pattern from awesome-design-md into tokens, layout rules, and AI-agent instructions that match the existing Vue 3 + Element Plus implementation.
---

# Mock API Frontend DESIGN.md

Use this file before changing `mockapi/frontend/src/App.vue`, `mockapi/frontend/src/style.css`, or the built static UI under `mockapi/web/static`.

## Product Role

The frontend is a DPU workflow control console. Its primary jobs are:

- register or connect a test account
- display active session context
- trigger mock workflow operations
- expose real-time logs and activity
- let an AI assistant help inspect or explain DPU execution context
- search historical logs without leaving the tool

Design for repeated operational use by testers and developers.

## Current Stack

- Vue 3 with `<script setup>`
- Vite
- Element Plus components and Element Plus icons
- Single-page app shell in `src/App.vue`
- Global styling in `src/style.css`

Do not introduce a UI framework or icon library unless the user explicitly asks. Reuse Element Plus and the existing CSS variable approach.

## Core Tokens

The existing CSS already defines the most important tokens. Keep these names stable when possible:

```css
:root {
  --surface: rgba(255, 255, 255, 0.88);
  --surface-strong: #ffffff;
  --text: #152033;
  --muted: #5d6b82;
  --line: rgba(21, 32, 51, 0.1);
}
```

Dark mode is controlled by `:root.mockapi-dark`. Any new component must have an acceptable dark-mode state.

## Local Color Roles

| Role | Preferred Value | Use |
|---|---:|---|
| App canvas | `#f5f8fb` | Body background |
| Dark canvas | `#08121c` | Dark body background |
| Primary action | `#00684a` | Main execution and connected state |
| Secondary action | `#0d5dd3` | AI, links, secondary commands |
| Success | `#14804a` | Success and approved results |
| Warning | `#b7791f` | Processing and pending states |
| Error | `#c0392b` | Failed, rejected, exception |
| Log dark | `#0d2133` | Payload/result strips |

Use color as a status signal, but always include a text label.

## Layout Rules

### App Shell

- Keep `.app-shell` constrained and centered.
- Main console view should expose the operation area and side context without requiring a landing-page scroll.
- Use `.workspace-grid` for main content plus side content:
  - left: registration, connection, operation forms
  - right: session summary, logs, activity, AI entry points

### Header Panel

- The current `.hero-panel` is an operational header. Keep it compact.
- Header actions should be visible, but they should not cover the title on small screens.
- Do not add marketing claims or feature explanation blocks here.

### Cards

- Use `.surface-card` for top-level panels.
- Use `.form-block`, `.activity-item`, and `.log-entry` for repeated bounded items.
- Do not nest decorative cards inside decorative cards.
- Repeated operation blocks should be easy to scan by title, endpoint, description, fields, and action.

### Forms

- Keep forms tight and predictable.
- Fixed-value workflow fields should use selects.
- Amounts should use numeric inputs.
- Full-width rows should use `.full-row`.
- If a field is conditional, keep the condition close to the status field that controls it.

### Logs And Payloads

- Use monospace for logs, SQL, JSON, identifiers, request/response bodies.
- Long payload text must wrap or scroll without changing the layout width.
- Empty states should be quiet and useful, not illustrative.

### AI Drawer

- The AI drawer is secondary to the workflow console.
- Keep resize behavior and full-width mobile behavior.
- Show environment context near AI execution controls.
- AI messages should be readable, but not styled like customer chat; this is an internal diagnostic assistant.

## Component Patterns

| Pattern | Existing Class | Guidance |
|---|---|---|
| Main panel | `.surface-card` | Top-level tool or context panel |
| Form grouping | `.form-block` | A concrete operation setup area |
| Operation list | `.operation-panels` | Workflow action groups |
| Result surface | `.result-strip` | Success payload, redirect URL, or command output |
| Session metadata | `.summary-row` | Label/value pairs with safe long-value wrapping |
| Log row | `.log-entry` | Timestamp plus payload in `pre` |
| Activity row | `.activity-item` | Short event summary |
| AI message | `.chat-message`, `.chat-bubble` | Internal assistant transcript |

## Responsive Rules

- Below `900px`, drawers should become full-width and resize handles should be hidden.
- Below tablet width, collapse operation fields and dual panels to one column.
- Buttons and inputs should stay at least 40px tall.
- Avoid horizontal page scroll. Allow scroll only inside code/log blocks where needed.

## Accessibility And Safety

- Do not use color-only status.
- Preserve visible focus states from Element Plus.
- Keep destructive or failure-state operations visually distinct.
- Do not place primary action buttons in positions where they can be confused with refresh, theme toggle, or drawer open controls.
- Text inside buttons and cards must not overflow in Chinese or English.

## Agent Instructions

When an AI agent edits this frontend:

1. Read root `DESIGN.md` and this file first.
2. Preserve Vue 3 + Element Plus patterns.
3. Keep changes scoped to `src/App.vue`, `src/style.css`, or documented frontend files unless the task requires backend API changes.
4. Update dark-mode styling for every new visual surface.
5. Run `npm run build` from `mockapi/frontend` after code changes.
6. If the generated static app is served by FastAPI, copy or rebuild assets only through the repo's existing build process.

## Useful Prompt

```text
Use mockapi/frontend/DESIGN.md. Improve this screen as an internal DPU workflow console:
- keep Element Plus
- keep dense operation-first layout
- show env/session/status context clearly
- keep logs and JSON readable
- support light and dark mode
- avoid marketing layout and decorative cards
```

