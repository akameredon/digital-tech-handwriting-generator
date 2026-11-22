# Open Handwriting Recognition — Architecture Decision

## Status

A controlled, optional worksheet path and an experimental natural-page analysis path are implemented. The natural-page path can use an explicitly configured local HTR provider, propagate character geometry, gate glyph candidates on defensible geometry, localize uncertainty for teacher review, and learn only from explicit confirmations. It is **not approved as a production handwriting-recognition service** because real teacher-labelled acceptance data and deployment evidence are still absent.

## Product decision

The intended product should accept natural handwriting samples as its primary handwriting input. The generated worksheet is an optional calibration path only; teachers can still create standard printable lesson PDFs without printing or scanning it. Worksheet cell positions are used only for that generated, labeled sheet, never to assign labels to arbitrary notebook pages.

The worksheet flow asks the teacher to confirm that each written character matches the printed label. That confirmation is a human self-check, not a vision-model verification. A wrong character in a cell can still be mislabeled if the teacher does not catch it. The UI and export response must not describe this as automatic handwriting recognition.

## Current implementation status

- `GET /handwriting/calibration-sheet` creates a generated A4 landscape worksheet. Its code-marked corners and grid are checked before use.
- `POST /export/handwriting-pdf` accepts only an image matching that worksheet, requires explicit label confirmation, compiles detected cell crops into a partial font, and creates a lesson PDF. Unsupported characters use Helvetica. The result reports the number of covered characters.
- The worksheet is optional for the product overall. The ordinary ruled printable-PDF route needs no handwriting sample.
- `POST /analyze/handwriting` performs natural-page intake, line analysis, optional explicitly configured local HTR, geometry-aware alignment, and localized review evidence. It does not silently promote uncertain labels into glyphs.
- `POST /analyze/handwriting/confirm` promotes only teacher-selected candidates and records provenance/evidence in the writer profile flow.
- TrOCR and Kraken adapters are lazy and optional. No model is implicitly downloaded, and no provider is enabled unless configured by the deployment environment.
- The dataset-driven validation CLI reports CER/WER and geometry/review metrics and refuses synthetic-only manifests as real-data acceptance.

## Safety contract

A recognized text string without character geometry is not enough to create a personalized glyph. Missing, malformed, low-confidence, out-of-bounds, or count-mismatched geometry becomes localized review evidence. Unicode labels are never guessed from character order, connected-component order, or x-position. Only explicit geometry plus teacher confirmation can enter the writer-profile learning flow.

## Limits and risks

A printed label plus a known cell location supplies a proposed Unicode identity; it is not proof that the ink in the cell has that shape. The endpoint cannot determine whether the teacher copied the printed label correctly. It rejects unrelated pages and large or crowded cells, but cannot semantically verify every character. The teacher confirmation is therefore necessary, and the generated PDF reports partial coverage. Missing glyphs are omitted from the custom font and rendered with standard text instead of synthetic rectangles.

The historical arbitrary-page positional mapper remains unsuitable for natural writing. Removing row-count checks or labeling components by horizontal position would not solve the absence of recognized Unicode identities.

## Production acceptance still required

1. Supply a consented, human-transcribed set of representative teacher pages.
2. Run `scripts/validate_natural_handwriting.py` with `real_data: true` and review CER, WER, page-review, and geometry-candidate metrics.
3. Test varied natural notebook layouts, the supplied `IMG_3492` if available, human-ground-truth character/word error rates, correction workflow, mobile use, and PDF visual regression.
4. Measure cold-start/warm latency and memory in the target hosting environment before enabling a provider there.
5. Complete accessibility, deployment-preview, rollback, monitoring, and explicit release-approval gates.

## Model and hosting constraints

A large model must not be loaded into the free Render web process without memory and latency measurements. A lightweight CPU-first model or separate worker may be needed. Do not add a paid OCR service, external provider dependency, new hosting spend, or production model download without approval.

Candidate references for evaluation are Kraken HTR, TrOCR handwritten, and the TrOCR paper. Research notes and implementation sources are recorded in [HTR_RESEARCH_NOTES.md](HTR_RESEARCH_NOTES.md).

## API direction

The natural-page API intentionally returns recognized text, page-coordinate geometry, confidence, alternatives, review reasons, candidate/missing evidence, provider metadata, and explicit fallback warnings. It remains an experimental opt-in path until the production acceptance evidence above exists.

Return specific 4xx errors for unsupported or unreadable scans. Log unexpected failures with a correlation ID and traceback while returning a safe user message.

## Acceptance status

- Partial font compilation and omission of unsupported cmap entries are implemented and tested.
- PDF fallback to standard text and coverage reporting are implemented and tested.
- Generated worksheet layout, orientation markers, grid validation, arbitrary-page rejection, and teacher label confirmation are tested.
- Local HTR adapters, geometry-safe alignment, confirmation-to-profile learning, validation reports, request correlation, smoke gates, and runtime benchmarking are implemented and tested.
- Real teacher-labelled recognition quality, representative mobile/device acceptance, deployment preview, rollback, monitoring, and public release approval remain open.
- Production deployment must wait for the natural-page release gates and measured resource use. The optional worksheet does not satisfy those gates.

## Explicit non-goal

Do not make a rigid template a requirement for ordinary Lesson Studio use. An optional worksheet can provide a controlled, teacher-confirmed sample for the experimental font path, but ordinary natural handwriting remains the intended input for a future fully accepted recognition feature.
