# BrewGraph Web

This is the Quasar frontend for BrewGraph OSS.

## Layout

- `src/core/` — a framework-free package of BrewGraph client logic. Other
  BrewGraph clients can vendor this directory on its own, pinned to a specific
  commit of this repository.
- `src/modules/`, `src/views/`, `src/fragments/` — application adapters,
  stores, Vue presentation, and API integration.

The core must not depend on Vue, Pinia, a UI library, authentication, a network
client, browser APIs, or application-specific API calls. Application code adapts
core functions to its own state, permissions, wording, and UI.

## Theme

Quasar brand colours live in `src/ui/theme.ts`; the matching CSS variables
(font stack, radius, palette, light/dark) live in `src/styles/app-theme.css`.

## Development

Start the active frontend from this directory:

```sh
npm run dev  # http://localhost:5174
```

Vite uses the configured strict development port so it fails clearly if that
port is already in use.

The OSS private-registry build pipeline packages this frontend as the
`brewgraph-web` image. Docker Hub publication remains a separate manual release
step.
