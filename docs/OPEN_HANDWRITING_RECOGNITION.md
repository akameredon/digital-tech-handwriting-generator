# Open Handwriting Recognition — Architecture Decision

Status: proposed implementation plan; not yet implemented or deployed.

## Product decision

D.Lesson Studio accepts natural handwriting samples. A fixed six-row character sheet, fixed row count, fixed order, and mandatory punctuation row are not product requirements. The six-row sheet may remain as an optional calibration aid, but it must never be required.

The uploaded sample is evidence of a writer's style, not a positional character key.

## Existing blockers verified in main

- ingestion/preprocessor.py requires exactly six row bands and maps components to DEFAULT_SAMPLE_ROWS by left-to-right position.

- main.py explicitly passes DEFAULT_SAMPLE_ORDER into that preprocessor.

- model/font_compiler.py rejects any glyph set that does not contain every character in REQUIRED_CHARS.

- renderer/pdf_exporter.py requires a complete alphabet and digit cmap before registering the custom font.

- frontend/src/App.tsx instructs users to upload the complete sample sheet.

- main.py catches all unexpected exceptions and returns the same generic 422 message without logging the traceback.

Removing only the row-count check would be unsafe: extracted image components have no Unicode identity unless a recognizer or a human correction supplies it.

## Proposed pipeline

1. Image intake and quality assessment: accept a full notebook page, exercise-book page, or multiple natural handwriting lines. Correct orientation and perspective where possible; estimate blur, exposure, crop, and resolution. Return actionable quality guidance without requiring a prescribed layout.

2. Layout analysis: detect page regions, text lines, word regions, and line bounding boxes. Treat notebook ruling and shadows as image artefacts, not character rows. Preserve coordinates so recognizer output can be linked back to source crops.

3. Handwritten text recognition: put recognition behind a provider interface returning text, region geometry, confidence, and model metadata. Evaluate Kraken for line segmentation plus HTR and TrOCR handwritten for line-crop recognition. TrOCR is line-level, so it requires a preceding line detector. Benchmark on real teacher handwriting, including supplied IMG_3492, before selecting a default. Do not use generic printed-text OCR or x-position to assign character labels.

4. Writer profile and glyph evidence: align recognized text with image regions; use character alignment only when defensible offsets or a correction workflow supplies them. Store glyph observations with Unicode label, crop, confidence, source region, and provenance. Aggregate multiple examples of the same character; retain variants. Never turn an uncertain OCR guess into a confirmed glyph.

5. Progressive font generation: compile fonts from the observed, confirmed subset rather than requiring a complete fixed alphabet. Build a valid .notdef glyph and cmap only for confirmed characters. Use explicit fallback for missing characters in the PDF and tell the teacher which characters were not represented by their sample. Do not claim synthetic or fallback glyphs are the teacher's handwriting.

6. Teacher correction: present only low-confidence words/characters for review. Corrections update text-to-image alignment and writer profile. A single uncertain character must not invalidate the entire upload.

7. PDF rendering: use personalized glyphs wherever supported and explicit fallback elsewhere. Preserve wrapping, punctuation, line spacing, page boundaries, and notebook appearance. Render every page to images for regression inspection.

## Model and hosting constraints

No HTR model/provider is currently configured in the repository. Render is on the free service tier, so a large transformer must not be loaded into the production web process without memory/latency measurements.

Candidate references for evaluation:

- Kraken HTR: https://github.com/mittagessen/kraken

- TrOCR handwritten: https://huggingface.co/microsoft/trocr-base-handwritten

- TrOCR paper: https://arxiv.org/abs/2109.10282

A lightweight CPU-first HTR model or separate worker may be necessary. Keep the app usable if recognition is unavailable: explain the limitation and do not fall back to the old fixed-template rejection path. Do not add a paid OCR API, external service dependency, or new hosting spend without approval.

## API contract direction

Replace the implicit all-or-nothing font build with a structured result containing recognized_text; regions with page coordinates and transcription; uncertain_regions with confidence and correction state; glyph_coverage with observed/confirmed/missing character sets; font_status (ready_partial, needs_correction, or recognition_unavailable); and warnings describing fallback glyph use.

Return specific 4xx errors only for genuinely unreadable/unsupported uploads. Log unexpected server failures with a correlation ID and traceback; return a safe message that does not misdiagnose software failures as bad handwriting.

## Acceptance gates

- Supplied IMG_3492 image is accepted for natural-layout analysis without a six-row-template check.

- Varied notebook pages, line counts, spacing, ruling, and mixed case are accepted.

- Recognition is evaluated against human transcription; report character/word error rates.

- No positional label assignment is allowed.

- Ambiguity is localized for correction; no silent wrong mappings.

- Partial fonts compile and PDF fallback is explicit.

- Tests cover cmap, glyph shape/proportion, punctuation, line wrapping, page boundaries, and multiple pages.

- CI renders generated PDF pages to images and runs visual regression checks.

- iPhone upload, correction, generation, download, and reopening the PDF are tested end to end.

- Production deploy waits for passing gates and a measured memory/latency profile compatible with the free tier.

## Explicit non-goal

Do not make a rigid template the required way to use D.Lesson Studio. An optional calibration worksheet may improve coverage, but ordinary handwriting must remain the primary supported input.