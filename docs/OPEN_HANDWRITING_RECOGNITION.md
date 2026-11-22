# Open Handwriting Recognition — Architecture Decision

Status: a controlled, optional worksheet path is implemented for experimental handwriting-style PDFs. Natural-page handwriting recognition and model-based text-to-glyph alignment remain unavailable. This repository is not being presented as production-ready.

## Product decision

The intended product should accept natural handwriting samples as its primary handwriting input. The generated worksheet is an optional calibration path only; teachers can still create standard printable lesson PDFs without printing or scanning it. Worksheet cell positions are used only for that generated, labeled sheet, never to assign labels to arbitrary notebook pages.

The worksheet flow asks the teacher to confirm that each written character matches the printed label. That confirmation is a human self-check, not a vision-model verification. A wrong character in a cell can still be mislabeled if the teacher does not catch it. The UI and export response must not describe this as automatic handwriting recognition.

## Current implementation status

- `GET /handwriting/calibration-sheet` creates a generated A4 landscape worksheet. Its code-marked corners and grid are checked before use.
- `POST /export/handwriting-pdf` accepts only an image matching that worksheet, requires explicit label confirmation, compiles detected cell crops into a partial font, and creates a lesson PDF. Unsupported characters use Helvetica. The result reports the number of covered characters.
- The worksheet is optional for the product overall. The ordinary ruled printable-PDF route still needs no handwriting sample.
- Natural notebook pages are not recognized or accepted by the calibration endpoint. No HTR provider is configured or called from the export route.
- `ingestion/open_handwriting.py` retains a provider contract and natural-page analysis components, but they do not establish recognition or character-level alignment.

## Limits and risks of the worksheet path

A printed label plus a known cell location supplies a proposed Unicode identity; it is not proof that the ink in the cell has that shape. The endpoint cannot determine whether the teacher copied the printed label correctly. It rejects unrelated pages and large or crowded cells, but cannot semantically verify every character. The teacher confirmation is therefore necessary, and the generated PDF reports partial coverage. Missing glyphs are omitted from the custom font and rendered with standard text instead of synthetic rectangles.

The historical arbitrary-page positional mapper remains unsuitable for natural writing. Removing row-count checks or labeling components by horizontal position would not solve the absence of recognized Unicode identities.

## Natural-page pipeline still required

1. Assess full notebook pages or handwriting lines for orientation, crop, blur, exposure, and resolution without requiring a prescribed layout.
2. Detect page regions, text lines, word regions, and bounding boxes while treating notebook ruling and shadows as image artifacts.
3. Put HTR behind a provider interface that returns recognized text, region geometry, confidence, and model metadata. Evaluate Kraken for line segmentation and HTR, and TrOCR for line-crop recognition. TrOCR needs a separate line detector and neither candidate alone guarantees character geometry.
4. Align text with image regions. Persist glyph observations only when Unicode labels and crops are defensible or confirmed through correction. Preserve confidence, source coordinates, and provenance.
5. Compile only observed and confirmed glyphs. Use explicit fallback for missing characters and tell the teacher which characters were not represented.
6. Localize uncertainty for teacher correction instead of silently turning an OCR guess into a font glyph.
7. Render every PDF page for layout and visual regression checks.

## Model and hosting constraints

No HTR model/provider is configured. A large model must not be loaded into the free Render web process without memory and latency measurements. A lightweight CPU-first model or separate worker may be needed. Do not add a paid OCR service, external provider dependency, new hosting spend, or production model download without approval.

Candidate references for evaluation are Kraken HTR, TrOCR handwritten, and the TrOCR paper. Research notes and implementation sources are recorded in [HTR_RESEARCH_NOTES.md](HTR_RESEARCH_NOTES.md).

## API direction

The worksheet API is intentionally narrow: generated-sheet input, explicit `confirm_labels`, validated crops, and a coverage/fallback result. A natural-page API should not be enabled until it can return recognized text, regions with page coordinates and transcription, uncertain regions with confidence/correction state, confirmed/observed/missing glyph coverage, a readiness status, and explicit fallback warnings.

Return specific 4xx errors for unsupported or unreadable scans. Log unexpected failures with a correlation ID and traceback while returning a safe user message.

## Acceptance status

- Partial font compilation and omission of unsupported cmap entries are implemented and tested.
- PDF fallback to standard text and coverage reporting are implemented and tested.
- Generated worksheet layout, orientation markers, grid validation, arbitrary-page rejection, and teacher label confirmation are tested.
- Recognition on the supplied `IMG_3492`, varied natural notebook layouts, human-ground-truth character/word error rates, correction UI, iPhone end-to-end use, PDF visual regression, and free-tier memory/latency measurements remain open.
- Production deployment must wait for natural-page release gates and measured resource use. The optional worksheet does not satisfy those gates.

## Explicit non-goal

Do not make a rigid template a requirement for ordinary Ink Flow Handwriting Studio use. An optional worksheet can provide a controlled, teacher-confirmed sample for the experimental font path, but ordinary natural handwriting remains the intended input for a future complete recognition feature.
