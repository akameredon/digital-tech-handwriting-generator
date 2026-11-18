# Changelog

## [1.0.0] – 2026-11-18

### Added
- Full official NERDC 2025 Digital Technologies schemes (SS1–SS3)
- Pedagogical prompt engine + validator
- OpenCV handwriting preprocessor
- Contour-based TrueType font compiler (real vector outlines from glyphs)
- Classmate-style PDF exporter with custom handwriting font support
- End-to-end pipeline script (`scripts/end_to_end_pipeline.py`)
- FastAPI service with `/health`, `/lesson`, `/topics`, `/prompt`
- CLI tool with `--pdf` support
- 30+ ready classroom lesson notes across SS1–SS3
- Teacher Guide, Sample Sheet instructions, Contributing guide
- GitHub Actions CI, Docker + docker-compose, Makefile
- Pipeline smoke tests
- 2-up print helper (for exercise book pasting)

### Sample Notes Cover
- SS1: Foundations, Number Systems, Hardware, Software, OS, Networks, Internet, Cybersecurity, Privacy, Spreadsheets, Word Processing, Presentation
- SS2: Programming (Algorithms → Python → Control Structures), Data Science, Big Data, AI, ML, Web Design, Spreadsheets, Blockchain, Digital Entrepreneurship, Cybersecurity III
- SS3: Advanced Programming, OOP, SDLC, IoT, Advanced Web, SQL

### Known Limitations
- Glyph quality depends heavily on the clarity of the handwriting sample
- Cursive/connected writing is not fully handled
- Some scheme weeks still return skeleton notes (use `--prompt` to expand)
