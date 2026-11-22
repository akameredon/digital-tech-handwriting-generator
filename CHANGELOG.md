# Changelog

## [Unreleased]

### Added
- Added an optional generated handwriting calibration worksheet and a worksheet-only PDF export path with teacher label confirmation.
- Added partial-font compilation, explicit standard-text fallback for missing characters, and API coverage reporting.
- Added worksheet validation, arbitrary notebook-page rejection, API integration tests, and research notes for future natural-page HTR work.
- Added local HTR provider adapters, geometry-gated character alignment, teacher confirmation flow, progressive writer-profile learning, and deterministic natural-page validation gates.

### Limitations
- Real teacher-labelled handwriting data, accessibility evidence, deployment-preview evidence, and explicit public-release approval are still required before natural-page handwriting recognition can be called production-ready.

## [1.1.2] – 2026-11-19

### Fixed
- Replaced hard-coded prepared-note paths with a metadata-driven resolver shared by the API and CLI.
- Corrected the SS1 First Term hardware note to Week 4, matching the hardware, storage, and input/output curriculum content; Week 5 remains an outline for the Midterm Test.
- Added a standard printable ruled-PDF endpoint and CLI flow.
- Disabled handwriting-font PDF generation until genuine handwriting recognition and text-to-glyph alignment are available. Legacy calls receive a clear `503` instead of a misleading PDF.
- Fixed Python package discovery and included prepared Markdown notes in built distributions.
- Added a committed npm lockfile and switched Docker/CI installs to `npm ci`.
- Corrected UI copy, stale lesson state handling, lesson-count documentation, and launch status claims.

### Verification
- 32 Python tests passed; TypeScript checks and the Vite production build passed.
- `npm audit --omit=dev --audit-level=high` reported zero shipped dependency vulnerabilities.
- A clean wheel built successfully, included all 26 lesson files, and ran the installed `dt-notes` command.
- Live HTTP smoke checks passed for health, prepared lesson lookup, printable PDF export, and the safe handwriting-endpoint `503` response.
- Docker was not available in this sandbox, so the image build still needs its CI run. Real teacher handwriting recognition is not implemented in this release.

## [1.0.0] – 2026-11-18

### Added
- Encoded Digital Technologies scheme data for SS1–SS3.
- Pedagogical prompt engine and validator.
- OpenCV handwriting preprocessing and a glyph-font compiler (the browser handwriting export is currently disabled; see v1.1.2).
- Classmate-style printable PDF exporter.
- FastAPI service, CLI, Docker configuration, and GitHub Actions CI.
- 26 Markdown lesson files, each aligned to an encoded curriculum week.
- Teacher guide, sample-sheet research notes, contributing guide, and 2-up print helper.

### Known limitations
- Some weeks return curriculum outlines rather than full prepared notes.
- The project does not currently include a handwriting-recognition model or text-to-glyph alignment pipeline.
- The encoded scheme may differ from local school calendars and should be checked by teachers.
