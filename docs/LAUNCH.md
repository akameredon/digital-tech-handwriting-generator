# Release readiness

## Current status

The curriculum, lesson-note, standard printable-PDF, teacher web interface, and natural-page handwriting engineering paths are present in the repository. The core application can be launched as a curriculum and printable lesson service.

The application is **not yet approved for a public handwriting-recognition launch**. This is intentional: real teacher-labelled pages are not committed to the repository, so recognition quality, CER/WER, and teacher acceptance remain unverified. The validation harness reports this honestly and refuses to treat synthetic-only data as real-world acceptance evidence.

## Verified in this repository

- Backend suite: 102 tests passed locally.
- Frontend TypeScript check and production build: passed locally.
- Local API smoke checks: `/health`, `/ready`, `/`, `/topics`, and standard lesson-PDF export passed; the legacy handwriting export remains explicitly gated.
- Local runtime benchmark passed the configured p95/error budgets for the core endpoints; target-environment latency and memory evidence are still required.
- Natural-page validation infrastructure is committed, deterministic, and includes CER/WER, geometry review-rate, candidate-rate, and real-data gates.
- Uncertain character geometry is localized for review rather than silently accepted, and Unicode labels are not inferred from positional order.
- `origin/main` is the source of truth for the completed work.

## Required before a public handwriting release

1. Supply a consented, human-transcribed set of representative teacher pages and run `scripts/validate_natural_handwriting.py` with `real_data: true`.
2. Review the resulting CER/WER, page-review, and geometry-candidate metrics; fix failures rather than changing thresholds to force a pass.
3. Complete the keyboard, screen-reader, contrast, mobile, and reduced-motion checks in `docs/FRONTEND_IMPLEMENTATION_GATES.md`.
4. Run a deployment preview with safe test data, verify logs, memory/latency, upload limits, rollback, and provider configuration. Do not expose model credentials to the browser.
5. Obtain explicit release approval before changing the deployment service or presenting natural-page handwriting recognition as production-ready.

## Local verification

```bash
python -m pytest tests/ -q
cd frontend && npm ci && npm run build
```

Docker image construction remains a CI/deployment-environment check when Docker is unavailable locally. A green test/build run is necessary but does not replace real-data, accessibility, security, or deployment-preview evidence.

Until the handwriting gates above are met, launch the core lesson and printable-PDF workflow only, and describe natural-page handwriting recognition as an experimental, gated capability.
