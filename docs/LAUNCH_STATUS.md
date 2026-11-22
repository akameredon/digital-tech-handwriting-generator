# Launch status matrix

Updated after Workstream 8. The repository is synchronized with `origin/main` at the current release commit.

## Green — complete in the repository

| Area | Evidence |
|---|---|
| Curriculum, lesson notes, and standard printable PDFs | 102 backend tests, live API smoke checks, and PDF signature/content checks pass locally. |
| Teacher web interface | TypeScript check and Vite production build pass. |
| Natural-page engineering path | Optional provider adapters, geometry-safe alignment, localized review, confirmation-to-profile learning, and validation CLI are implemented. |
| Safety and operations | Upload limits, security headers, request IDs, `/health`, `/ready`, deployment smoke gate, and runtime benchmark are implemented. |
| CI | Docker build, frontend build, backend suite, container smoke checks, deployment smoke gate, and conservative runtime budget command are configured. |
| Documentation | Launch, teacher, provider, validation, operational, and performance boundaries are documented without claiming unverified accuracy. |

## Amber — finish with browser/device evidence

| Hold | Required action | Owner/input |
|---|---|---|
| Accessibility and responsive acceptance | Test mobile, tablet, desktop, keyboard-only, focus order, screen reader semantics, contrast, reduced motion, slow network, and browser console behavior. | A real browser/device test session or CI browser environment. |
| Preview acceptance | Run the smoke gate and runtime benchmark against the actual preview URL, not localhost. | Preview URL and safe test data. |

## Red — cannot be truthfully completed from this repository alone

| Hold | Why it blocks the handwriting launch | Required input |
|---|---|---|
| Real handwriting quality | No consented teacher pages with human transcriptions are present. Synthetic pages cannot establish CER/WER or teacher acceptance. | A labelled manifest of real teacher pages and transcriptions. |
| Provider production choice | TrOCR/Kraken are optional adapters; no provider/model is enabled by default. | Approved local model/provider choice and deployment resource budget. |
| Hosting resource evidence | Local benchmarks do not prove Render/free-tier memory, cold-start, or sustained latency. | Target deployment preview and observed logs/metrics. |
| Rollback and monitoring | Rollback has not been executed against a real deployment. | Deployment access, known-good SHA, rollback record, and monitoring owner. |
| Public release approval | The repository cannot authorize production publication by itself. | Explicit release approval from the project owner. |

## What can launch now

The curriculum browsing, prepared/outlined lesson workflow, teacher web interface, and standard printable lesson-PDF service can be launched as the core product after a deployment preview and owner approval. Natural-page handwriting recognition must remain labelled experimental/gated until the red holds are satisfied.

## Exact next handoff

1. Provide the preview URL and safe test credentials/data, if applicable.
2. Provide the real labelled handwriting manifest, or explicitly defer handwriting recognition from the initial launch.
3. Confirm whether the initial public launch is **core lesson/PDF only** or includes experimental handwriting analysis.
4. Approve the deployment and rollback action after preview evidence is recorded.
