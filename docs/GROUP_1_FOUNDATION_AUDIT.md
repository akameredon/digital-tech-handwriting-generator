# Group 1 — Product Foundation Audit and Implementation Blueprint

**Audit date:** 2026-11-22  
**Repository:** `akameredon/digital-tech-handwriting-generator`  
**Baseline inspected:** `main` at `8d43fa87bae981fea47b2fed3b597ce722f55993`  
**Working branch:** `feat/group-1-foundation-audit`  
**Scope:** Repository-level static audit, workflow trace, product acceptance definition, and architecture decisions. No production code, curriculum content, customer data, or deployment settings changed by this document.

> This is an evidence-backed engineering baseline, not a production-readiness declaration. Static source inspection is not a substitute for executing the test suite or testing with real teacher handwriting.

## 1. Executive decision

The product target is:

> A teacher uploads an ordinary handwritten notebook page or lesson note. The system analyzes the page, recognizes the writing, asks the teacher to correct only uncertain regions, builds a reusable profile from confirmed handwriting observations, generates a complete lesson note, renders that note in the teacher's handwriting style, and returns a printable PDF.

The current repository is a useful curriculum/PDF application with an experimental worksheet-based font path and a natural-page image-analysis foundation. It is **not yet** the target natural-handwriting recognition and generation product.

The safe implementation strategy is incremental and adapter-based:

1. Preserve the existing curriculum, lesson retrieval, standard PDF, and optional worksheet experiment.
2. Build natural-page intake as a separate workflow; do not route ordinary pages through positional worksheet labeling.
3. Benchmark real HTR models before choosing or hosting one.
4. Treat recognized text, character geometry, and teacher-confirmed glyph identity as separate evidence.
5. Build a progressive handwriting profile from confirmed observations.
6. Keep lesson content generation independent from handwriting rendering.
7. Render PDFs deterministically and inspect the resulting pages.

## 2. Repository inventory

### Runtime and application layers

| Layer | Current location | Observed responsibility |
|---|---|---|
| HTTP application | `main.py` | FastAPI routes, lesson payloads, PDF endpoints, upload limits |
| Curriculum source | `curriculum/nerdc_schemes.py` | Encoded NERDC topic/content lookup |
| Lesson prompt builder | `curriculum/prompt_engine.py` | Builds prompts; does not call an AI model |
| Prepared-note index | `curriculum/sample_notes.py` | Indexes Markdown notes by metadata and curriculum topic |
| Curriculum validation | `curriculum/validator.py` | Exam/break-week and lesson validation helpers |
| Natural-page analysis foundation | `ingestion/open_handwriting.py` | Loads an image, detects horizontal text-line regions, exposes an injected HTR protocol |
| Worksheet preprocessing | `ingestion/preprocessor.py` | Connected components and positional labels for the known worksheet/sample order |
| Worksheet creation/validation | `ingestion/calibration_sheet.py` | Creates and validates the generated calibration sheet |
| Font compiler | `model/font_compiler.py` | Builds a partial TrueType font from supplied labeled glyph images |
| PDF renderer | `renderer/pdf_exporter.py` | Ruled lesson PDF generation and optional custom-font use |
| Teacher frontend | `frontend/src/App.tsx`, `frontend/src/api.ts` | React + TypeScript curriculum, lesson review, worksheet and PDF workflows |
| Frontend build | `frontend/package.json`, `frontend/vite.config.ts` | Type-check/build with Vite |
| Packaging | `pyproject.toml`, `requirements.txt` | Python package and dependencies |
| Container | `Dockerfile`, `docker-compose.yml` | Node build stage and Python/FastAPI runtime |
| Hosted service config | `render.yaml` | Render Docker web service, free plan, Ohio region, /health check |
| CI | `.github/workflows/ci.yml` | Python tests, frontend typecheck/build, dependency audit, Docker build and smoke checks |

### Repository-level facts

- Python package requires Python `>=3.10`; the Docker runtime uses Python 3.11.
- Frontend build uses Node 22, React 19, TypeScript and Vite.
- The application uses FastAPI/Uvicorn, OpenCV, Pillow, NumPy, fontTools and ReportLab.
- No HTR model package, model weight, model-serving process, or paid OCR provider is configured in `requirements.txt` or the inspected application path.
- The README reports 26 prepared Markdown lesson notes and 39 encoded weekly curriculum entries per class for SS1–SS3. Weeks without a matched prepared note return an outline; the prompt endpoint returns a prompt for an external AI tool.
- The application currently has two distinct PDF concepts: a standard ruled printable PDF and an experimental handwriting-style PDF based on a generated, labeled calibration worksheet.

## 3. Current end-to-end workflow trace

### Existing standard lesson PDF

`GET /topics` → teacher selects class/term/week → `GET /lesson/{class_level}/{term}/{week}` → `build_lesson_payload()` → prepared Markdown note or curriculum outline → `POST /export/lesson-pdf` → `ClassmatePDFExporter` → temporary PDF → browser download.

This is a real standard-PDF workflow. It does not claim to reproduce the teacher's handwriting.

### Existing experimental worksheet handwriting PDF

`GET /handwriting/calibration-sheet` → teacher prints and fills the generated worksheet → `POST /export/handwriting-pdf` with `calibration_scan` and `confirm_labels` → calibration-sheet validation/extraction → `FontCompiler` → `ClassmatePDFExporter` → PDF download.

This path uses the known worksheet labels/cells and explicit teacher confirmation. It is not natural-page OCR. The teacher confirmation is a self-check, not machine verification.

### Natural-page foundation is currently disconnected

`ingestion/open_handwriting.py` contains an image loader, horizontal projection line segmentation, a `HandwritingRecognizer` protocol, and a `ConfiguredRecognizer` that fails explicitly if no provider is injected. The inspected `main.py` does not import or call this module from either PDF export route. It therefore does not currently provide a teacher-facing natural-page upload/recognition workflow.

## 4. Worksheet assumptions and unsafe shortcuts identified

1. The worksheet endpoint expects the generated calibration-sheet format and validates its markers/grid.
2. The worksheet UI asks the teacher to print, fill and upload that specific sheet.
3. `ingestion/preprocessor.py` uses `DEFAULT_SAMPLE_ORDER` as the label sequence for extracted components. That is only defensible for the controlled sheet, not an arbitrary notebook page.
4. The natural-page analyzer returns line regions, not Unicode-labeled character regions.
5. A line-level transcription does not automatically supply verified character crops.
6. Removing row-count or template checks without a recognizer/alignment/correction stage would create unlabeled or incorrectly labeled glyphs.
7. The font compiler accepts partial labeled glyph sets (at least eight usable characters in the inspected implementation); partial compilation does not prove that the labels are correct or that the output resembles the writer.
8. A missing glyph must be reported and use an explicit fallback. It must never be silently represented as a teacher-observed glyph.

**Decision:** Keep worksheet-specific assumptions isolated in the worksheet experiment. The natural-page route must have its own request model, analysis pipeline, recognizer adapter, correction state, provenance model and acceptance tests.

## 5. Current HTTP/API surface

| Method | Path | Purpose | Current state |
|---|---|---|---|
| GET | `/` | Serves built frontend or fallback HTML | Implemented |
| GET | `/health` | Health/version response | Implemented |
| GET | `/lesson-form` | Legacy selection redirect | Implemented |
| GET | `/topics` | Curriculum topic listing | Implemented |
| GET | `/lesson/{class_level}/{term}/{week}` | Lesson payload | Implemented |
| GET | `/prompt/{class_level}/{term}/{week}` | Prompt text for an external AI tool | Implemented; no model call |
| POST | `/export/lesson-pdf` | Standard ruled PDF | Implemented |
| GET | `/handwriting/calibration-sheet` | Generate optional experimental worksheet | Implemented |
| POST | `/export/handwriting-pdf` | Worksheet-only handwriting-style PDF | Implemented; not natural-page HTR |
| GET | `/docs`, `/openapi.json` | FastAPI API documentation/schema | Framework-provided |

The frontend API client currently covers topics, lesson retrieval, prompt retrieval, standard PDF export, calibration-sheet download and worksheet PDF export. It does not expose a natural-page recognition client.

### Required future API boundaries

The natural-page workflow should be added as versionable, independently testable operations, for example:

- create an upload/analysis job;
- retrieve page and line analysis;
- retrieve recognition results with model/version/confidence and source coordinates;
- submit teacher corrections for selected uncertain regions;
- retrieve writer-profile coverage and readiness;
- create a lesson-render job using a selected profile;
- retrieve job status and download the final PDF.

These are proposed boundaries, not claims that these routes already exist. Exact route names and persistence semantics should be finalized in the implementation design before coding.

## 6. Duplicate/unused-code and dependency audit boundary

The repository inventory and key execution paths were inspected. The current code clearly has distinct standard-PDF and worksheet-PDF paths, and a natural-page analysis module that is not wired into the export path.

A complete unused-symbol/import graph, duplicate-function scan, and dependency reachability report has **not** been executed in this environment. No code should be deleted on the basis of naming or apparent non-use alone. Before cleanup, run a local static analysis/import graph and verify package entry points, CLI scripts, tests, Docker build and deployment imports. Any cleanup must be a separate, minimal change with regression evidence.

No HTR package or model dependency should be added until model benchmarking establishes a candidate and resource budget.

## 7. Product acceptance criteria

The product acceptance contract is grounded in GitHub issue #4, “Replace rigid handwriting template with open handwriting recognition.”

A teacher must be able to:

1. Upload ordinary notebook pages, exercise-book pages or naturally written lesson notes without a prescribed row count, grid, character order or punctuation checklist.
2. Upload pages with varied line counts, spacing, ruling and mixed uppercase/lowercase writing.
3. Receive page/line/word regions with coordinates and a real model transcription.
4. See which recognized regions are uncertain and correct only those regions.
5. Have corrected/confirmed glyph observations linked to their transcription, source image, coordinates, confidence and provenance.
6. Build a progressive writer profile from multiple examples and repeated characters.
7. Generate useful output with partial character coverage while seeing which glyphs are missing and which fallback is used.
8. Select or create a lesson with honest content status (prepared note versus outline versus generated/teacher-edited content).
9. Render a complete lesson in the selected handwriting profile.
10. Download a readable PDF and use the workflow on a mobile device.

System acceptance must additionally verify:
- recognition accuracy against human-corrected ground truth;
- alignment accuracy for any glyph extraction method;
- no silent positional Unicode labeling on natural pages;
- secure upload handling and temporary-file cleanup;
- explicit error IDs and server-side tracebacks for unexpected failures;
- correct PDF character coverage, wrapping, page boundaries and font embedding;
- visual inspection of every generated page;
- mobile upload, correction, preview and download;
- measured CPU, memory, latency and model footprint on the intended hosting tier.

## 8. Initial supported scope proposal

To avoid an unbounded first release, use this proposed initial scope unless real sample evaluation shows it is unsuitable:

- **Language/script:** English, Latin alphabet, Arabic numerals and common English punctuation. This matches the current English-language lesson content. Do not claim support for other scripts until separately benchmarked.
- **Input:** JPG/JPEG and PNG photographs/scans first; add multi-page PDF ingestion after the single-page pipeline is stable.
- **Page types:** ordinary ruled/unruled notebook pages, exercise-book pages and lesson-note pages; no fixed worksheet requirement.
- **Capture:** mobile camera photo and file upload; image quality feedback before expensive recognition.
- **Recognition:** model output is a hypothesis with confidence and coordinates, never ground truth. Human correction is the authority for ambiguous text/glyph labels.
- **Profile:** progressive, versioned, writer-owned profile with observed/confirmed/unsupported character coverage.
- **Output:** standard printable PDF always remains available; personalized handwriting PDF only when profile coverage and fallback disclosures are sufficient.
- **Hosting:** benchmark CPU-first/self-hostable candidates against actual resource limits before choosing a deployment architecture. Do not add paid APIs, paid hosting or automatic model downloads without approval.

This is a proposed v1 scope, not a statement that the current app already supports all of it.

## 9. Test and CI baseline

### Existing test inventory

The repository contains test modules covering:
- calibration sheet creation/validation;
- curriculum;
- handwriting export and PDF structure;
- handwriting release gates;
- natural-page image analysis and recognizer-unavailable behavior;
- pipeline smoke tests;
- worksheet preprocessor;
- prepared lesson notes;
- web application routes;
- standard PDF web export.

The CI workflow is configured to run Python tests, frontend typecheck/build, a production dependency audit, Docker build and a container smoke test. It is configured for pushes to `main` and pull requests targeting `main`; a feature-branch push alone does not trigger that workflow.

### Test-quality limitations

- The natural-page test fixture uses OpenCV-generated script-style computer text (`cv2.putText`), not a real teacher's handwriting.
- The release-gate font tests use synthetic geometric blobs, not recognized real glyphs.
- A successful synthetic segmentation/font/PDF test cannot establish HTR accuracy, real character alignment or handwriting-style fidelity.
- The repository's test configuration does not itself report a coverage percentage.
- No fresh test execution, frontend build, Docker build, PDF visual inspection or mobile-device test was performed as part of this static audit.
- No baseline model latency, peak memory, CPU throughput or model download size has yet been measured.

**Baseline status:** test inventory and CI configuration identified; live execution and quantitative performance baseline remain pending.

## 10. Architecture blueprint and dependency order

### Proposed modular components

1. **Upload boundary:** MIME/content validation, byte limits, safe temporary storage, page count and job ID.
2. **Page preparation:** orientation, page boundary, perspective, blur/glare/contrast and ruling analysis.
3. **Layout analysis:** text blocks, lines, words and coordinate transforms retained back to the original page.
4. **HTR adapter:** provider-neutral interface with model name/version, text, confidence and region metadata.
5. **Correction layer:** region-level teacher correction, immutable original prediction and correction provenance.
6. **Alignment layer:** recognizer-provided character cuts or a separately validated alignment method; unsupported/failed alignment remains unavailable.
7. **Glyph observation store:** Unicode label, crop, source page, coordinates, model evidence, human confirmation, confidence and duplicate/variant identity.
8. **Writer profile:** observed glyph variants, spacing/slant/size/stroke statistics, coverage, profile version and quality/readiness.
9. **Lesson content service:** curriculum lookup, prepared-note status, actual generation provider if approved, teacher editing and content validation.
10. **Handwriting renderer:** profile-aware glyph selection, natural variation, metrics, fallback and reproducible layout.
11. **PDF exporter:** deterministic page geometry, fonts, page flow, metadata and export manifest.
12. **Quality/operations:** structured logs, correlation IDs, job lifecycle, privacy retention, metrics and acceptance evidence.

### Recommended processing order

Upload → image quality/page preparation → layout/line segmentation → HTR → confidence and correction → text-to-image alignment → confirmed glyph observations → progressive writer profile → lesson content selection/generation/editing → profile-aware rendering → PDF export → page-by-page inspection → download.

### Provider selection rule

Benchmark Kraken first because its toolkit includes segmentation and recognition-related geometry, then compare TrOCR for line recognition where useful. Do not assume either model provides trustworthy character crops for every script or handwriting style. Record:
- model/checkpoint and version;
- license and redistribution constraints;
- supported script/language;
- model size and download footprint;
- cold-start and warm latency;
- peak memory and CPU usage;
- line/word error rate on ground-truth samples;
- character alignment success/failure rate;
- unsupported-character behavior;
- operational compatibility with the target host.

Select a model only after a real teacher sample is available and the measurements are recorded.

## 11. Group 1 task ledger

| # | Task | Status | Evidence / remaining work |
|---:|---|---|---|
| 1 | Audit repository and classify features | COMPLETE — static | Repository tree, README, main routes, frontend, curriculum, ingestion, font, renderer, tests, packaging, CI and deployment config inspected. |
| 2 | Map frontend/backend architecture | COMPLETE — static | Architecture inventory in Sections 2 and 5. |
| 3 | Trace upload-to-PDF execution | COMPLETE — static | Standard and worksheet flows traced in Section 3; natural-page path identified as disconnected. |
| 4 | Identify worksheet assumptions | COMPLETE — static | Section 4 identifies fixed worksheet and positional-label assumptions and the safe boundary. |
| 5 | Map APIs and schemas | PARTIAL | Routes and frontend client mapped; complete generated OpenAPI/schema review and contract tests remain. |
| 6 | Identify duplicate/unused code | PARTIAL | Main execution paths and disconnected natural-page module identified; full import/symbol graph and duplicate scan remain. No speculative deletion made. |
| 7 | Define teacher acceptance criteria | COMPLETE | Section 7 aligns the product contract to open issue #4. |
| 8 | Define initial language/format scope | COMPLETE — proposed | Section 8 defines a bounded v1 scope; real sample evaluation may revise it. |
| 9 | Establish test/performance baseline | PARTIAL | Test inventory and CI trigger behavior documented; fresh test run, coverage, device, PDF visual and performance measurements remain. |
| 10 | Produce dependency-based blueprint | COMPLETE — design | Section 10 defines modules, processing order and model-selection evidence. |

## 12. Group 1 exit decision

**Group 1 is NOT fully passed yet.** Static foundation and architecture work is recorded, but tasks 5, 6 and 9 still need executable evidence.

The remaining closure work is:
1. Export/review the live OpenAPI schema and add contract assertions for the existing routes.
2. Run a repository-wide static import/symbol/dependency analysis locally and review every proposed cleanup before changing code.
3. Run the full Python suite, frontend typecheck/build and Docker CI; record exact run URLs and commit SHA.
4. Establish a real-device/PDF baseline and a performance measurement plan. HTR performance measurements must wait until a model and real sample are selected.
5. Obtain at least one real teacher handwriting sample with a known transcription before claiming natural-page recognition accuracy.

### Release guardrails

- No natural-page character label may be inferred from a fixed x/y position or a presumed alphabet order.
- No HTR provider is selected solely from benchmark reputation.
- No paid API, paid service, or new hosting spend is introduced without explicit approval.
- No real teacher image is sent to an external provider without an approved privacy/data-handling decision.
- No production-ready claim until the full teacher workflow passes real-sample and real-device acceptance.
- No merge or production deployment is authorized by this document.
