# Gate 1 — Frontend Baseline and Preservation Audit

**Repository:** `akameredon/ink-flow-handwriting-studio`.
**Audit date:** 2026-11-18
**Baseline branch:** `main`
**Baseline commit inspected:** `f531207df799731930917a7beb0c9096145fed76`  
**Scope:** Read-only architecture and source inspection. No production code or curriculum files changed.

> This is a historical snapshot of the stated baseline commit, not a description of the current v1.1.2 code. See the repository README and current release notes for present behavior.

## Executive finding

The repository is a Python-first application. It does not currently contain a dedicated React/Vue/Svelte frontend, JavaScript package manifest, frontend build configuration, or static frontend directory. The current homepage is HTML generated inside the FastAPI `main.py`.

This is a good opportunity to add a separate, modern teacher-facing frontend while keeping the existing Python domain logic and CLI as the source of truth. The safe integration is additive: a frontend client calls existing FastAPI read routes and new, separately tested API routes only where web workflows are currently missing.

## Repository inventory

### Existing core and protected paths

- `curriculum/nerdc_schemes.py` — in-repository curriculum data and lookup functions; documented in source as the single source of truth.
- `curriculum/prompt_engine.py` — prompt construction.
- `curriculum/validator.py` — lesson structure and exam/break validation.
- `ingestion/preprocessor.py` — handwriting image preprocessing and glyph extraction.
- `model/font_compiler.py` — TrueType font compilation.
- `renderer/pdf_exporter.py` — Classmate-style ruled PDF export.
- `renderer/two_up.py` — additional PDF layout helper.
- `scripts/generate_note.py` — command-line lesson retrieval and prompt output.
- `scripts/end_to_end_pipeline.py` — CLI handwriting image → glyphs → TTF → PDF pipeline.
- `scripts/bulk_generate.py` — bulk lesson workflow.
- `samples/**` — prepared lesson-note content.
- `tests/**` — curriculum, preprocessor and pipeline smoke tests.
- `Dockerfile`, `docker-compose.yml`, `run.sh`, `Makefile`, `requirements.txt`, `pyproject.toml` — Python runtime, packaging and local/container workflows.
- `.github/workflows/ci.yml` — current GitHub Actions test workflow.

These paths are protected from UI-only rewrites. Any future change to a protected path must be narrowly additive, justified, reviewed and regression-tested.

### Current runtime and dependencies

- Python package requires Python `>=3.10`; Docker uses Python 3.11.
- FastAPI and Uvicorn provide the HTTP application.
- OpenCV, Pillow and NumPy support image processing.
- fontTools supports font compilation.
- ReportLab and fpdf2 are present for PDF-related work.
- No Node package manifest or frontend dependencies exist on the inspected baseline.
- Existing deployment examples are local execution and Docker Compose. No Vercel, Cloudflare Pages, Render, Railway or other hosted deployment configuration was found in the inspected tree.

## Existing HTTP surface in `main.py`

| Method | Path | Current behavior |
|---|---|---|
| GET | `/` | Returns a basic HTML page with class, term and week selectors and quick links. |
| GET | `/health` | Returns service health and version. |
| GET | `/lesson-form` | Redirects the form selection to the lesson route. |
| GET | `/topics` | Returns curriculum topics, optionally filtered by class. |
| GET | `/lesson/{class_level}/{term}/{week}` | Returns lesson metadata, official content, exam/break flag and lesson-note text as JSON. |
| GET | `/prompt/{class_level}/{term}/{week}` | Returns a generated LLM prompt as JSON. |

The app also exposes FastAPI's interactive documentation through its standard `/docs` route.

### Important web-workflow gaps

The current HTTP app does **not** expose an upload endpoint for handwriting samples, a browser-accessible font-compilation workflow, or a PDF download endpoint. Those steps currently live in the CLI pipeline. The prompt endpoint returns a prompt; it does not call an LLM to generate a lesson note.

Therefore, the frontend must not pretend that browser-based AI generation, handwriting upload, or PDF export already works. Gate 3 may add small, separately tested HTTP adapters that call the existing Python modules and preserve the CLI. No new lesson-generation engine or duplicate curriculum store should be created.

## Test and CI baseline evidence

Three test files are present:

- `tests/test_curriculum.py`
- `tests/test_preprocessor.py`
- `tests/test_pipeline_smoke.py`

The latest inspected GitHub Actions run on the original `main` baseline commit `f531207df799731930917a7beb0c9096145fed76` completed successfully on 2026-11-18. The original workflow ran curriculum and preprocessor tests but omitted `tests/test_pipeline_smoke.py`.

The feature branch expands CI to run the complete `tests/` directory and the frontend type-check/build. GitHub Actions run [44247418513](https://github.com/akameredon/ink-flow-handwriting-studio/actions/runs/44247418513), on feature commit `3d3462a9e0b5de1668e591b62daaedb54e198a7b`, completed successfully: **16 Python tests passed**, including the font compiler and PDF exporter smoke tests, and the frontend type-check, production build and application import checks all passed.

**Execution limitation:** this audit used the repository source and remote GitHub Actions evidence; it did not execute a fresh local clone/test run in this environment.

## Preservation contract

1. Keep `main` as the production baseline; all UI work remains on a feature branch.
2. Do not rewrite the curriculum, samples, lesson prompts, validators, handwriting preprocessor, font compiler, PDF renderer or CLI.
3. Keep existing route paths and response semantics backward-compatible.
4. Add new web routes as adapters around existing Python functions, not as replacement business logic.
5. Do not introduce a second curriculum database or copy the NERDC scheme into frontend source.
6. Keep upload processing temporary and bounded; validate file type/size and clean up generated artifacts after response.
7. Keep secrets and model credentials out of browser code.
8. No production merge or deployment without all five release gates and explicit release approval.

## Gate 1 result

**Static architecture inventory: PASS.** The application structure, protected paths, current HTTP routes, CLI workflows, dependencies, CI configuration and key frontend integration gaps have been identified.

**Full automated runtime baseline: PASS.** The complete Python test suite and frontend type-check/build have passed on the feature branch. Manual browser, device, accessibility and real sample-sheet verification remain Gate 4 work.

## Recommended next step

Gate 1 is complete and the Gate 2 design specification is recorded in `docs/TEACHER_UI_DESIGN_SPEC.md`. The initial Gate 3 implementation is on the feature branch. Continue Gate 4 with real browser/device checks and a real teacher sample-sheet upload before any production release.

## Frontend dependency advisory note

The initial full dependency audit found a high-severity advisory for the transitive `picomatch` dependency used by Vite's build tooling (GHSA-fc5q-39xc-vjpf / CVE-2026-112366). The advisory describes a ReDoS pattern and currently lists picomatch releases through 4.0.7 as affected; the public advisory does not list a patched release. Upstream discussion disputes whether the reported behavior constitutes a vulnerability in normal usage. See the [GitHub advisory](https://github.com/advisories/GHSA-fc5q-39xc-vjpf).

The affected dependency is in the frontend **development/build toolchain**, not the browser runtime bundle. The Docker build copies only the compiled static assets into the Python runtime image; it does not copy Node.js, Vite, or `node_modules`. The build does not accept untrusted glob patterns. We therefore keep the supported Vite 7 toolchain, report all build-time advisories in CI, and enforce `npm audit --omit=dev --audit-level=high` for shipped frontend dependencies. We will revisit the exception when upstream publishes a patched picomatch release or the dependency path changes. We do not force a major downgrade solely to silence the advisory.
