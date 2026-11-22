# Workstream 6 — operational readiness

## Scope

Workstream 6 adds deployment-safe operational signals without exposing secrets or changing business behavior.

- Every HTTP response receives an `X-Request-ID`. A safe caller-supplied ID is preserved for support correlation; malformed or oversized values are replaced with a short generated ID.
- `GET /ready` exposes a small readiness contract containing service/version, whether the compiled frontend is present, and whether an HTR provider is configured. It never returns model paths, credentials, or environment values.
- CI container smoke tests exercise `/ready` and assert that request correlation is present.

`/health` remains the liveness endpoint. `/ready` describes the application state visible to deployment checks; absence of an HTR provider is reported as configuration state because the curriculum and printable-PDF application intentionally work without the optional handwriting provider.

## Verification

- Regression tests cover readiness fields and safe/unsafe request-ID behavior.
- The CI Docker smoke test checks `/health`, `/ready`, the frontend, topics, and the request-ID response header.
- The full Python suite and frontend production build remain required.

## Boundaries

This does not prove a deployment preview, rollback, uptime, latency, memory budget, or real teacher-handwriting accuracy. Those still require the target hosting environment, representative safe test data, and explicit release approval. No provider is downloaded or enabled by this workstream.
