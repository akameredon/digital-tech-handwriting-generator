# Digital Technologies Lesson Note Generator
**NERDC 2025 • SS1 – SS3 • Production Ready v1.0.0**

Generate high-quality, curriculum-aligned lesson notes for Digital Technologies that Nigerian secondary school teachers can use immediately.

**Repository:** https://github.com/akameredon/digital-tech-handwriting-generator

---

## Quick Start (Tomorrow Morning)

```bash
git clone https://github.com/akameredon/digital-tech-handwriting-generator.git
cd digital-tech-handwriting-generator
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Get any lesson note
python scripts/generate_note.py --class SS2 --term "Second Term" --week 2

# List all topics
python scripts/generate_note.py --list SS1

# Start the web API
./run.sh
# → http://127.0.0.1:8000/docs
```

Or with Docker:
```bash
docker compose up --build
```

---

## Teacher Web App

The repository now includes a separate React + TypeScript teacher interface. The Python curriculum, handwriting and PDF modules remain the source of truth.

### Run locally

Start the existing FastAPI service:

```bash
./run.sh
```

In a second terminal, start the frontend development server:

```bash
cd frontend
npm install
npm run dev
```

Open the Vite address shown in the terminal (normally `http://localhost:5173`). The development server proxies API requests to the FastAPI service on port 8000.

### Run with Docker

```bash
docker compose up --build
```

Open `http://localhost:8000`. The Docker build compiles the frontend and packages the static assets with the existing Python application.

The teacher interface supports curriculum browsing, lesson review, copying the existing curriculum-based AI prompt, and handwriting-sample upload for PDF export. The prompt route returns a prompt; it does not call an AI model. Uploaded handwriting samples are processed temporarily by the existing Python pipeline and are not intentionally retained as permanent uploads.

## What is Included

### Core System
- Full official NERDC 2025 Digital Technologies schemes (SS1–SS3)
- Pedagogical prompt engine + validator
- Handwriting preprocessor (OpenCV)
- Font compiler + Classmate-style PDF exporter
- FastAPI service with health check
- CLI tool
- GitHub Actions CI
- Docker + docker-compose support
- Teacher Guide + Sample Sheet instructions

### Ready Lesson Notes (30+)
**SS1** – Introduction, History, Number Systems, Hardware, Software, Operating Systems, Networks, Internet, Cybersecurity I & II, Data Privacy, Spreadsheets, Presentation Software  

**SS2** – Algorithms, Python, Variables, Control Structures, Data Science, Big Data, AI, Machine Learning, Web Design, Advanced Spreadsheet, Blockchain, Digital Entrepreneurship  

**SS3** – Advanced Programming (Functions/Lists), OOP, SDLC, IoT, Advanced Web Design, SQL Basics  

All notes follow the standard structure:  
Behavioral Objectives → Key Concepts → Explanation → Practical Example → Class Activity → Quick Test → Assignment

---

## Documentation
- [Teacher Guide](docs/TEACHER_GUIDE.md)
- [Handwriting Sample Instructions](docs/SAMPLE_SHEET_INSTRUCTIONS.md)
- [Contributing](docs/CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

---

## License
MIT – free for teachers and schools to use and modify.

Built to help Nigerian Digital Technologies teachers deliver curriculum-aligned lessons with confidence.
