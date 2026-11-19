# Release readiness — v1.1.2

## Current status: not production-ready

The current build provides curriculum browsing, prepared notes where the metadata agrees with the encoded curriculum, curriculum outlines, prompts for external AI tools, and standard ruled printable PDFs. Handwriting-to-font export is intentionally unavailable: no handwriting-recognition model or verified text-to-glyph alignment provider is configured. The compatibility endpoint returns `503` instead of creating a misleading font.

Do not describe or deploy this version as a production handwriting service. The UI must continue to describe the limitation until the recognition and alignment gates below are complete.

## Local verification

```bash
python -m pytest tests/ -q
cd frontend && npm ci && npm run build
```

The CI workflow additionally builds the Docker image and checks `/health`, `/`, and `/topics` in the running container. A green CI run is necessary but does not prove production readiness.

## Required before a production release

1. Configure and document a genuine handwritten-text recognition provider without exposing credentials to the browser.
2. Align recognized text to image regions, validate confidence, and ensure uncertain labels are never silently compiled as confirmed glyphs.
3. Test representative real teacher pages and report recognition accuracy; test missing-character fallback and PDF layout.
4. Complete the mobile, keyboard, screen-reader, contrast, and reduced-motion checks in `docs/FRONTEND_IMPLEMENTATION_GATES.md`.
5. Run a deployment preview with safe test data, verify rollback, record logs and memory/latency behavior, and obtain explicit release approval before production deployment.

Until then, teachers can use the standard printable PDF and the lesson/prompt workflows.
