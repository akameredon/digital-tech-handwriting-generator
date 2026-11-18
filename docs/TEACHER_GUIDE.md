# Teacher Guide – Digital Technologies Lesson Note Generator

**For Nigerian Secondary School Teachers (SS1–SS3)**

---

## 1. Quick Start (5 minutes)

```bash
git clone https://github.com/akameredon/digital-tech-handwriting-generator.git
cd digital-tech-handwriting-generator
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Get a lesson note immediately
```bash
python scripts/generate_note.py --class SS2 --term "Second Term" --week 2
```

### See all topics for a class
```bash
python scripts/generate_note.py --list SS1
```

---

## 2. What the notes contain

Every content week follows this structure:

1. **Behavioral Learning Objectives** – what students should be able to do
2. **Key Concepts / Definitions** – clear, age-appropriate definitions
3. **Step-by-Step Conceptual Explanation** – simple teaching notes
4. **Practical / Worked Example** – classroom-ready example (code or illustration)
5. **Class Activity** – 10–15 minute activity
6. **End-of-Lesson Quick Test** – 5 short questions
7. **Assignment** – take-home task

---

## 3. Recommended workflow for tomorrow

1. Check the scheme of work for the exact week.
2. Run the CLI command for that class, term and week.
3. Copy the output into your lesson note book or print it.
4. Adjust any local examples if needed (school name, local context).

---

## 4. Using the Web Interface

```bash
./run.sh
```
Then open: http://127.0.0.1:8000/docs

You can also open:
- http://127.0.0.1:8000/lesson/SS2/Second%20Term/2
- http://127.0.0.1:8000/topics

---

## 5. Notes already prepared

**SS1** – Introduction, History, Number Systems, Hardware, Software, Cybersecurity  
**SS2** – Algorithms, Python, Variables, Control Structures, Data Science, Big Data, AI, Machine Learning, Web Design  
**SS3** – OOP Basics, Software Development Life Cycle (SDLC)

More notes are being added continuously.

---

## 6. Tips for Nigerian classrooms

- The language is kept simple and suitable for SS students.
- Nigerian examples (MTN, Naira, local schools, JAMB, WAEC) are used where relevant.
- Code examples use Python because it is the most accessible language for secondary schools.
- You can freely edit any note to match your exact scheme or textbook.

---

**Questions or missing weeks?**  
Open an issue on the GitHub repository or generate the prompt with:

```bash
python scripts/generate_note.py --class SS1 --term "First Term" --week 8 --prompt
```

Then paste the prompt into any good AI tool to expand the note.
