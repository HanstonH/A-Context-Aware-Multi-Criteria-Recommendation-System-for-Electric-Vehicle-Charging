# Deploying the web frontend to Railway

The web frontend and the phone app share one backend: the Flask API in `backend/`,
already deployed on Railway (project `mapexplore-backend`, service `backend`). How to
deploy *that* is in `backend/README.md`. This page covers the web frontend only.

```
Browser ──► frontend (Next.js, Railway, public)
               └─► backend (Flask, Railway, public) ◄── phone app
```

The frontend's API routes call the backend from the server, so the browser never
talks to the backend directly and the backend's API key (if set) stays private.

## 1. Redeploy the backend first

The web map needs `GET /api/stations` and the context-aware ranking, both new in
`backend/`. Whoever owns the backend service redeploys it from the repo root:

```
railway up --service backend --ci
```

Accounts are new too and need storage that survives redeploys. On the backend service
(once): attach a volume at `/data` and set `USERS_DB_PATH=/data/users.db` and
`RAILWAY_RUN_UID=0`. Details in `backend/README.md` → Deploy.

Check: `https://<backend-domain>/api/stations` returns about 3,000 stations, and a
`POST /api/recommend` response contains `"method": "topsis"`.

## 2. Create the frontend service

In any Railway project: **+ New → GitHub Repo** → this repo, then:

| Setting | Value |
|---|---|
| Settings → Root Directory | `/frontend` (Railway picks up `frontend/Dockerfile`) |
| Settings → Networking | **Generate Domain** (your public URL) |
| Settings → Watch Paths (optional) | `/frontend/**` |

Variables:

```
BACKEND_URL=https://<backend-domain>
NEXT_PUBLIC_GOOGLE_MAPS_API_KEY=...
GEMINI_API_KEY=...
# only if the backend sets APP_API_KEY
BACKEND_API_KEY=...
# optional
NEXT_PUBLIC_GOOGLE_MAP_ID=...
```

`NEXT_PUBLIC_*` values are built into the JavaScript bundle, so changing one needs
a redeploy, not just a restart.

## 3. Before sharing the URL

- **Google Maps browser key** (`NEXT_PUBLIC_GOOGLE_MAPS_API_KEY`): anyone who opens
  the site can see it. In Google Cloud → Credentials, restrict it to *HTTP referrers*
  = your Railway domain, and to the Maps JavaScript API only. Set a daily quota.
- **Gemini key** (`GEMINI_API_KEY`, used by the web chat panel): stays server-side.
  Set a usage cap in Google AI Studio.
- **Rate limits:** the backend limits requests per IP. The frontend forwards each
  visitor's IP (`X-Forwarded-For`), so web users don't share one limit.

## Checking it works

- Sign up on the login screen, reload the page: you're still logged in. Log out: back to the login screen.
- The map shows about 3,000 stations across Taiwan.
- A recommendation answers in a few seconds. Low battery favours the nearest
  stations; high battery favours cheaper ones where prices are known (mostly Taipei).

## Running locally

```
backend/.venv/Scripts/python -m backend     # http://localhost:8000 (see backend/README.md)
cd frontend && pnpm dev                      # BACKEND_URL defaults to http://localhost:8000
```
