# Digital Technologies Lesson Studio

**NERDC 2025 scheme • SS1–SS3 • Version 1.1.2**

A Python/FastAPI lesson-note tool and teacher-facing web interface for Nigerian senior secondary Digital Technologies. It provides curriculum browsing, prepared lesson notes where available, curriculum outlines and prompts for other weeks, and ruled printable PDFs.

> **Readiness note:** convincing teacher-specific generation of unseen handwriting is not yet established. The legacy stroke renderer uses generic fallback shapes, synthetic joins, and may truncate long lines; the existing worksheet PDF path compiles a partial font and uses a conventional fallback. Neither is evidence of authentic teacher handwriting. A separate [experimental sample-backed workflow](docs/EXPERIMENTAL_WRITER_PDF.md) rejects missing characters rather than substituting fonts, but it reconstructs static ink rather than learning natural handwriting and has not been validated on a teacher's samples.

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

The interface supports curriculum browsing, lesson review, copying a curriculum-based prompt for use in a separate AI tool, and downloading regular ruled PDFs. The prompt endpoint does not call an AI model. The optional worksheet path uses known cell positions only on the generated sheet, requires teacher label confirmation, compiles a partial font, and reports missing-character fallback to standard text. It does not recognize arbitrary notebook pages, and the teacher confirmation is not machine verification. See [worksheet instructions](docs/SAMPLE_SHEET_INSTRUCTIONS.md) and the [recognition architecture decision](docs/OPEN_HANDWRITING_RECOGNITION.md).

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
- [Legacy and experimental stroke-handwriting prototypes](docs/STROKE_HANDWRITING_GENERATION.md)
- [Experimental sample-backed PDF workflow](docs/EXPERIMENTAL_WRITER_PDF.md)
- [Research-only HWT feasibility results](docs/RESEARCH_HWT_FEASIBILITY.md)
- [Writer-style learning and reconstruction](docs/WRITER_STYLE_LEARNING.md)
- [Character extraction and alignment](docs/CHARACTER_EXTRACTION_ALIGNMENT.md)
- [Handwritten-text recognition](docs/HANDWRITTEN_TEXT_RECOGNITION.md)
- [Natural handwriting variation](docs/NATURAL_HANDWRITING_VARIATION.md)
- [Page and handwriting segmentation](docs/PAGE_HANDWRITING_SEGMENTATION.md)
- [Handwriting-preserving image processing](docs/HANDWRITING_PRESERVING_IMAGE_PROCESSING.md)
- [Complete lesson-content generation](docs/COMPLETE_LESSON_CONTENT_GENERATION.md)
- [Notebook layout and PDF rendering](docs/NOTEBOOK_LAYOUT_AND_PDF_RENDERING.md)
- [Quality assurance and acceptance gates](docs/QUALITY_ASSURANCE_ACCEPTANCE.md)
- [Teacher correction and profile management](docs/TEACHER_CORRECTION_PROFILE_MANAGEMENT.md)
- [Optional worksheet instructions](docs/SAMPLE_SHEET_INSTRUCTIONS.md)
- [HTR research notes and sources](docs/HTR_RESEARCH_NOTES.md)
- [Launch readiness checklist](docs/LAUNCH.md)
- [Changelog](CHANGELOG.md)

## License

MIT. See [LICENSE](LICENSE).
