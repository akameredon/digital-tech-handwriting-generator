# Release readiness — next release after v1.1.2

## Current status: not production-ready

The current project provides curriculum browsing, prepared notes where metadata agrees with the encoded curriculum, curriculum outlines, prompts for external AI tools, and standard ruled printable PDFs. It also has an experimental optional worksheet-only handwriting-style PDF path. That path uses known cells on a generated worksheet, requires a teacher label confirmation, compiles a partial font, and reports fallback for missing characters.

Natural notebook-page handwriting recognition and verified model-based text-to-glyph alignment are not implemented. The teacher checkbox is a self-check, not machine verification. Do not describe or deploy this project as a production handwriting-recognition service. The optional worksheet does not satisfy the natural-page release gates below.

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

Until those gates are met, teachers can use the standard printable PDF and the lesson/prompt workflows. The calibration worksheet is an optional experiment, not a replacement for ordinary handwriting recognition.
