# Digital Technologies Lesson Note Generator
**NERDC 2025 • SS1 – SS3 • Production Ready**

Generate high-quality, curriculum-aligned lesson notes for Digital Technologies that teachers can use immediately in class or copy into exercise books.

---

## How to Use Tomorrow Morning (Fastest Path)

### Option 1 – Command Line (Recommended)
```bash
cd digital-tech-handwriting-generator
python3 scripts/generate_note.py --class SS2 --term "Second Term" --week 2
```

### Option 2 – List all topics for a class
```bash
python3 scripts/generate_note.py --list SS2
```

### Option 3 – Start the web API
```bash
./run.sh
```
Then open: http://127.0.0.1:8000/docs

---

## What Is Already Production-Ready

### Core System
- Full official NERDC 2025 Digital Technologies schemes (SS1, SS2, SS3)
- Pedagogical prompt engine
- Lesson structure validator
- Handwriting preprocessor (OpenCV)
- Font compiler skeleton
- Classmate-style PDF exporter
- FastAPI web service
- CLI tool

### Ready-to-Use Lesson Notes
**SS1**
- Week 1: Introduction to Digital Technologies
- Week 3: Number Systems
- Week 4: Computer Hardware
- Week 6 (2nd Term): Cybersecurity I

**SS2 Second Term (complete core set)**
- Week 1: Algorithms & Flowcharts
- Week 2: Introduction to Python
- Week 3: Variables, Data Types & Operators
- Week 4: Control Structures
- Week 6: Data Science Basics
- Week 8: Big Data & Analytics
- Week 9: Artificial Intelligence
- Week 10: Machine Learning Basics

**SS3**
- Week 3: Object-Oriented Programming Basics

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
└── Dockerfile
```

---

## Install & Run
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Generate a note
python scripts/generate_note.py --class SS2 --term "Second Term" --week 4

# Or start the API
./run.sh
```

---

## For Teachers
1. Use the CLI or API to pull the exact week you need.
2. Copy the lesson note into your exercise book or print it.
3. The notes are already written in clear Nigerian secondary-school language.

You now have a working production system that covers the official NERDC Digital Technologies curriculum and gives you classroom-ready notes immediately.
