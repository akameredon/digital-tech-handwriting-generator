# Digital Technologies Lesson Note Generator
**NERDC 2025 • SS1 – SS3 • Production Ready**

Generate high-quality, curriculum-aligned lesson notes for Digital Technologies that teachers can use immediately in class or copy into exercise books.

**Repository:** https://github.com/akameredon/digital-tech-handwriting-generator

---

## Use Tomorrow Morning (Fastest Path)

```bash
git clone https://github.com/akameredon/digital-tech-handwriting-generator.git
cd digital-tech-handwriting-generator
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Get any lesson note
python scripts/generate_note.py --class SS2 --term "Second Term" --week 2

# List all topics for a class
python scripts/generate_note.py --list SS1

# Start web API
./run.sh
# then open http://127.0.0.1:8000/docs
```

---

## What is Ready

### Core System
- Full official NERDC 2025 Digital Technologies schemes (SS1, SS2, SS3)
- Pedagogical prompt engine + validator
- Handwriting preprocessor (OpenCV)
- Font compiler (fontTools)
- Classmate-style PDF exporter
- FastAPI web service
- CLI tool
- Docker support

### Ready Lesson Notes
**SS1 First Term**
- Week 1: Introduction to Digital Technologies
- Week 2: History & Evolution
- Week 3: Number Systems
- Week 4: Computer Hardware
- Week 6: Computer Software

**SS1 Second Term**
- Week 6: Cybersecurity I

**SS2 Second Term (core programming & data set)**
- Week 1: Algorithms & Flowcharts
- Week 2: Introduction to Python
- Week 3: Variables, Data Types & Operators
- Week 4: Control Structures
- Week 6: Data Science Basics
- Week 8: Big Data & Analytics
- Week 9: Artificial Intelligence
- Week 10: Machine Learning Basics

**SS3 First Term**
- Week 3: Object-Oriented Programming Basics
- Week 4: Software Development Life Cycle (SDLC)

All notes follow the standard classroom structure:
Behavioral Objectives → Key Concepts → Explanation → Practical Example → Class Activity → Quick Test → Assignment

---

## Project Structure
```
digital-tech-handwriting-generator/
├── main.py                  # FastAPI application
├── run.sh                   # One-command start
├── scripts/generate_note.py # CLI tool
├── curriculum/              # NERDC schemes + prompt engine
├── ingestion/               # Handwriting sample processing
├── model/                   # Font compilation
├── renderer/                # Classmate PDF export
├── samples/                 # Ready lesson notes
├── requirements.txt
├── Dockerfile
├── LICENSE
└── .gitignore
```

---

## License
MIT License – free for teachers and schools to use and modify.

Built for Nigerian Digital Technologies teachers who need authentic, examination-ready lesson notes.
