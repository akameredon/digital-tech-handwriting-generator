# Digital Technologies Lesson Studio v1.1.2

## Changes

- All 26 prepared lesson notes are discovered from their Markdown metadata and available to both the API and CLI.
- Corrected the SS1 First Term hardware note to Week 4; Week 5 stays identified as the Midterm Test rather than receiving a hardware lesson.
- The teacher UI and CLI can create a standard ruled printable PDF.
- Handwriting-to-font generation is disabled until a real recognizer and reliable glyph/text alignment are configured. Legacy API requests return a clear `503` response.
- Python package discovery is explicit, sample Markdown is included in distributions, and the `dt-notes` command can be installed.
- Frontend dependencies are locked and Docker/CI use `npm ci`.

## Verification

Local checks passed: 32 Python tests, TypeScript and Vite production build, runtime dependency audit (zero vulnerabilities), clean wheel build/install, CLI smoke test, and live API/PDF/handwriting-disabled smoke tests. Docker was not available in the local sandbox; CI must still confirm the image build.

This release is not a claim of production readiness. Accessibility, real-device, security, deployment-preview, and teacher workflow gates still require evidence before public release. Handwriting recognition remains out of scope until an actual provider and human-verified alignment workflow are implemented.
