# DPU Mock API Frontend

Vue 3 + Vite frontend for the DPU Mock API console.

This is an internal workflow tool for DPU testing. It supports account registration, session connection, mock workflow operations, live logs, activity history, log search, and AI-assisted diagnostics.

## Stack

- Vue 3
- Vite
- Element Plus
- Axios
- Pinia and Vue Router are installed for expansion, though the current UI is primarily a single console surface.

## Local Development

Install dependencies:

```bash
npm install
```

Run the frontend dev server:

```bash
npm run dev
```

Build static assets:

```bash
npm run build
```

Preview the production build:

```bash
npm run preview
```

## Design Guidance

Before changing UI, read:

- `../../DESIGN.md`
- `./DESIGN.md`

The frontend should remain a dense DPU operational console, not a marketing page. Keep environment, session, workflow status, logs, and payloads visible and easy to scan.

## AI Agent Usage

Use this prompt when asking an AI agent to modify the UI:

```text
Read ../../DESIGN.md and ./DESIGN.md first. Update the Mock API frontend as an internal DPU testing console. Keep Vue 3 + Element Plus, preserve dark mode, keep logs/JSON readable, and make env/session/status context explicit.
```

After code changes, run:

```bash
npm run build
```

## Key Files

- `src/App.vue` - main console UI and workflow state
- `src/style.css` - global app styling, light/dark mode, layout rules
- `src/api.js` - backend API calls
- `public/icons.svg` - static icon asset
- `vite.config.js` - Vite configuration

