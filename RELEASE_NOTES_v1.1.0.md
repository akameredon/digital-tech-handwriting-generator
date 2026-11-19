# D.Lesson Studio v1.1.0 — Launch candidate

> **Superseded:** This historical launch candidate described handwriting upload and broader prepared-note coverage that were not verified. Current behavior is documented in [v1.1.2 release notes](RELEASE_NOTES_v1.1.2.md); handwriting-to-font export is disabled.

## Teacher experience
- Simple three-step flow: choose lesson → upload handwriting photo → download notebook PDF
- Auto-loads full curriculum notes (SS1–SS3 instructional weeks)
- Clear sample-sheet guidance + printable guide image
- PWA manifest for Add to Home Screen on phones

## Pipeline
- Strict six-row sample template with release gates
- Real phone photos supported where sample sheet is complete
- Safer glyph handling; no silent wrong-character mapping
- Measured PDF text wrapping

## Verify before go-live
1. `npm ci && npm run build` in `frontend/` (or Docker build)
2. `python -m pytest tests/ -q`
3. Deploy to Render; confirm `/health`
4. On a phone: upload an isolated-character sample sheet and download a PDF
