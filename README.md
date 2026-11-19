# Digital Technologies Lesson Studio

**NERDC 2025 scheme • SS1–SS3 • Version 1.1.2**

A Python/FastAPI lesson-note tool and teacher-facing web interface for Nigerian senior secondary Digital Technologies. It provides curriculum browsing, prepared lesson notes where available, curriculum outlines and prompts for other weeks, and ruled printable PDFs.

> **Readiness note:** this repository is not being presented as production-ready. Handwriting-to-font export is intentionally disabled until real handwritten-text recognition and verified text-to-glyph alignment are implemented. A regular printable PDF is available instead.

## Quick start

```bash
git clone https://github.com/akameredon/digital-tech-handwriting-generator.git
cd digital-tech-handwriting-generator
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Retrieve a prepared note or the curriculum outline for a week
python scripts/generate_note.py --class SS2 --term "Second Term" --week 2

# Create a standard ruled printable PDF
python scripts/end_to_end_pipeline.py --class SS2 --term "Second Term" --week 2 --output lesson.pdf

# Start the API and teacher web app
./run.sh
# API docs: http://127.0.0.1:8000/docs
```

Installable package and console command:

```bash
pip install .
dt-notes --class SS2 --term "Second Term" --week 2
```

Or use Docker:

```bash
docker compose up --build
```

## Teacher web app

The React + TypeScript interface is in `frontend/`; FastAPI remains the source of truth for curriculum and lesson data.

For local development, start the API with `./run.sh`, then in another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open the Vite address shown in the terminal, normally `http://localhost:5173`. Its development server proxies API requests to port 8000. With Docker, open `http://localhost:8000`.

The interface supports curriculum browsing, lesson review, copying a curriculum-based prompt for use in a separate AI tool, and downloading a regular ruled PDF. The prompt endpoint does not call an AI model. The handwriting endpoint remains for compatibility but currently returns `503`; enabling it requires code integration of a genuine recognizer and verified text-to-glyph alignment, not just configuration. It will not generate a falsely labeled handwriting font.

## Lesson-note coverage

The repository contains 26 Markdown lesson files. All **26** now match a class, term, week, and topic in the encoded curriculum and are available as prepared notes. The hardware lesson metadata was corrected to SS1 First Term Week 4; Week 5 remains a midterm and is not served as an instructional lesson. Weeks without a matched prepared note return an explicitly labeled curriculum outline and can provide a prompt for an external AI tool.

The built-in curriculum contains 39 weekly entries for each of SS1, SS2, and SS3. This data is the project’s encoded scheme; teachers should verify local school implementation and calendar differences.

## Tests and builds

```bash
python -m pytest tests/ -q
cd frontend && npm ci && npm run build
```

The CI workflow also builds the Docker image and smoke-tests the API. Green unit/build checks do not replace real-device, accessibility, security, or deployment-preview validation.

## Documentation

- [Teacher guide](docs/TEACHER_GUIDE.md)
- [Handwriting feature status and architecture](docs/OPEN_HANDWRITING_RECOGNITION.md)
- [Sample-sheet research notes](docs/SAMPLE_SHEET_INSTRUCTIONS.md)
- [Launch readiness checklist](docs/LAUNCH.md)
- [Changelog](CHANGELOG.md)

## License

MIT. See [LICENSE](LICENSE).
