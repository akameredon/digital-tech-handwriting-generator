# Experimental local worksheet trajectory PDF

This is an **experimental, limited prototype**, not a production handwriting solution. It uses confirmed positions on the project's fixed calibration worksheet, extracts static ink crops, skeletonizes them and draws those skeleton paths. It is **not ML, not a font, not arbitrary-page handwriting recognition, not a reconstruction of real pen order, pressure or motion, and not evidence of writer identity, authenticity, similarity or completion**. The user's confirmation is an assertion, not independent verification. It does not prove that the result resembles the teacher's handwriting. Disconnected marks and intersections can be ambiguous; crop-edge ink may have been clipped during extraction. Inspect the worksheet and output carefully. The renderer does not use synthetic joins or generic fallback glyphs.

The resulting **PDF is image-only: text is not selectable, searchable, or accessible to screen readers**. Keep a separate accessible copy of the original text. The command prints this warning on stderr. These pages are not notebook-ruled paper and do not reproduce the teacher's original raster. Keep and use samples only with appropriate consent.

## Prepare and run locally

Install the project's existing Python dependencies. Obtain the generated calibration worksheet as described in [`SAMPLE_SHEET_INSTRUCTIONS.md`](SAMPLE_SHEET_INSTRUCTIONS.md); fill its labeled cells and scan the **whole** sheet as a local JPG or PNG. Only labels and geometries from those fixed worksheet cells are used. This command does not accept arbitrary notebook-page photographs. It makes no network requests and never saves a profile or sample, but you should use local (not network-mounted) input and output directories and handle the files privately yourself. No sample should be committed or transmitted.

Run from the repository root (or give the absolute script path from another directory):

```bash
python scripts/experimental_writer_pdf.py \
  --worksheet /local/private/worksheet.png \
  --text-file /local/private/exact-text.txt \
  --output /local/private/result.pdf \
  --report /local/private/result-report.json \
  --confirm-labels --acknowledge-experimental
```

Both confirmation flags are mandatory. Confirm labels only after checking the scan and the actual handwritten marks in the worksheet's labeled cells. `--report` is optional. `--seed` optionally accepts a signed 64-bit integer (default 0); layout is deterministic for the same data, options and software versions.

Alternatively, select a repository **prepared** curriculum-matched lesson:

```bash
python scripts/experimental_writer_pdf.py \
  --worksheet /local/private/worksheet.jpg \
  --class SS2 --term 'Third Term' --week 9 \
  --output /local/private/lesson.pdf \
  --confirm-labels --acknowledge-experimental
```

Choose exactly one source: `--text-file`, **or** all of `--class`, `--term` and `--week`. Class must be SS1, SS2 or SS3; term is `First Term`, `Second Term` or `Third Term`; week is 1–13. A missing prepared lesson is an error: no lesson is invented and no outline is substituted. Prepared notes are read as their exact UTF-8 Markdown, including markup. Many existing notes include punctuation (for example curly quotes or en dashes) not on the worksheet, and **will fail** even if every worksheet cell was filled. Providing a supported-character text file is an alternative, but editing/translating that file is the user's explicit action; the CLI never makes such changes.

## Strict coverage and layout

Text is decoded as UTF-8 **without** newline conversion, BOM stripping, Unicode normalization, Markdown interpretation, substitutions or truncation. Only ASCII space, tab and LF are layout characters. For every other code point, the confirmed worksheet must supply the exact character, with exact case and punctuation. CR/CRLF, non-ASCII whitespace, controls, missing labels and other unsupported characters fail. Error messages list each unsupported character and its **zero-based Python Unicode code-point offsets** in the source. These diagnostics may reveal characters from private text; protect stderr logs. Check or edit the original input explicitly and run again. There is no lowercase, punctuation, font or generic fallback.

The command verifies that every non-layout source character has exactly one ordered renderer placement and that all placements lie inside the drawable bounds before making the PDF. Spaces/tabs/LFs are accounted for as layout, not drawn glyphs. When a space or tab causes wrapping, the renderer consumes it as the line boundary; long words may wrap between characters. This accounting does not certify visual legibility, similarity or accessibility. Blank text (only space/tab/LF) is rejected.

Every output page is a complete 1240 × 1754 raster fitted proportionally and centered on A4 portrait, at approximately 150 DPI. No rendered page is cropped or stretched to fit. The original worksheet extraction itself can exclude grid/label areas and may clip ink that touches crop edges; ambiguity warnings should not be ignored. All rendered pages are included, including layout-driven blank pages, subject to limits.

## Limits, output safety and privacy

- Worksheet input: at most 12 MiB encoded, 12 million decoded pixels, and 6000 pixels per side; ingestion also requires a sufficiently large, properly oriented complete worksheet with its grid, corner markers, and at least eight nonblank labeled cells. JPG/PNG format is checked from the file, not merely its name.
- Text: at most 40,000 UTF-8 bytes and 10,000 Unicode code points; no empty/blank source. The repository prepared-lesson index is limited to 256 Markdown files of at most 40,000 bytes each before indexing. These files are trusted local project data and should not be concurrently modified during indexing.
- Rendering: at most 8 pages; the underlying renderer also limits total transformed trajectory points and image pixels, and the sample-preparation APIs enforce crop, graph and work limits. A resource or layout limit is an error, never silent truncation. Inputs must be regular local files.
- The destination directory must already exist. `--output` must end in `.pdf`, and optional `--report` in `.json`; neither may already exist, including dangling symlinks. A race-safe atomic create-if-absent publishes each completed file without overwriting another file. The PDF is published last. If publishing either file fails, the command attempts to remove files it created and always removes its temporary files during normal error handling. A PDF and report cannot be published as one atomic transaction: the report can briefly appear first. A process crash, forced termination or filesystem failure can leave a private `.experimental-writer-*` temporary file or a report; inspect and remove such leftovers. Temporary files use restrictive permissions. Output PDF and report themselves should be stored securely.
- The optional JSON contains counts, source kind, image/page dimensions, and per-page placement offsets plus offsets for spaces, tabs and LFs. It contains **no source text, worksheet path, lesson path, glyph labels or profile**. Offsets reveal document length and layout patterns, so the report is still sensitive metadata. It is an audit aid, not a handwriting-quality report. Stdout only names the output file, not its path or lesson contents. Unsupported-character diagnostics on stderr intentionally disclose characters and offsets.

The implementation does not touch the existing production endpoints or other scripts. For focused synthetic tests, run:

```bash
python -m pytest -q tests/test_experimental_writer_pdf.py tests/test_calibration_sheet.py \
  tests/test_teacher_ink.py tests/test_teacher_stroke_generation.py
```

The PDF inspection assertions use Poppler tools if available; they are optional for the test suite, not new runtime dependencies.
