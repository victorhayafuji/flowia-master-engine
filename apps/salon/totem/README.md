# FlowIA Totem (kiosk PWA)

Standalone self-service kiosk for the salon counter. A customer can **book**, **check in**
to an existing appointment, and ask **FAQ** questions — all driven by the same FastAPI
backend as the dashboard (channel `totem`).

It is a separate Vite app (own manifest + service worker) so its offline shell never caches
the admin dashboard.

## How it works

- **Auth = device token.** No person logs in. The token (generated in the dashboard at
  **Configurações → Totem**) is pasted once on the pairing screen and kept in `localStorage`.
  Every request sends it as the `x-device-token` header; the backend resolves the org from it
  (fail-closed → 403). A 403 unpairs the device.
- **Flow:** attract → identify (name + phone) → LGPD consent → menu (Agendar / Check-in /
  Dúvidas) → guided steps → confirmation → back to attract.
- **Privacy:** after a terminal step or 90s idle, the screen resets — no customer data lingers
  on a shared device.

## Run locally

```bash
cp .env.example .env   # point VITE_API_URL at your backend
npm install
npm run dev            # http://localhost:5174
```

## Build / deploy

```bash
npm run build          # tsc + vite build → dist/
```

Deploy `dist/` as a static site (e.g. a separate Render static service). Open the URL on the
tablet, add to home screen, and pair with a device token.
