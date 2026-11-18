"""
Digital Technologies Handwriting Lesson Note Generator
FastAPI entry point - production ready for teacher use.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pathlib import Path
import uvicorn
from typing import Optional

from curriculum.nerdc_schemes import get_lesson, list_all_topics
from curriculum.prompt_engine import build_prompt
from curriculum.validator import is_exam_or_break_week

app = FastAPI(
    title="Digital Technologies Lesson Note Generator",
    description="NERDC 2025 aligned lesson notes for SS1-SS3 Digital Technologies",
    version="1.0.0"
)

SAMPLES_DIR = Path(__file__).parent / "samples"


@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <html>
    <head><title>Digital Technologies Lesson Note Generator</title>
    <style>body{font-family:system-ui,sans-serif;max-width:900px;margin:40px auto;padding:0 20px}h1{color:#1a237e}.card{background:#f5f5f5;padding:16px;border-radius:8px;margin:12px 0}a{color:#0d47a1}code{background:#e3f2fd;padding:2px 6px;border-radius:4px}</style>
    </head>
    <body>
        <h1>Digital Technologies Lesson Note Generator</h1>
        <p>NERDC 2025 • SS1 – SS3 • Production Ready</p>
        <div class="card">
            <h3>Quick Links</h3>
            <ul>
                <li><a href="/docs">API Documentation (Swagger)</a></li>
                <li><a href="/topics">List all topics</a></li>
                <li><a href="/lesson/SS2/Second%20Term/2">Example: SS2 Second Term Week 2 (Python)</a></li>
            </ul>
        </div>
        <div class="card">
            <h3>How to use</h3>
            <ol>
                <li>Open <code>/docs</code></li>
                <li>Use <code>GET /lesson/{class_level}/{term}/{week}</code></li>
                <li>Copy the generated lesson note</li>
            </ol>
        </div>
    </body>
    </html>
    """


@app.get("/topics")
async def get_topics(class_level: Optional[str] = None):
    return list_all_topics(class_level)


@app.get("/lesson/{class_level}/{term}/{week}")
async def get_lesson_note(class_level: str, term: str, week: int):
    lesson = get_lesson(class_level, term, week)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found in official NERDC scheme")

    known_samples = {
        ("SS2", "Second Term", 1): SAMPLES_DIR / "SS2_Second_Term" / "Week01_Computer_Programming_I.md",
        ("SS2", "Second Term", 2): SAMPLES_DIR / "SS2_Second_Term" / "Week02_Introduction_to_Python.md",
        ("SS2", "Second Term", 3): SAMPLES_DIR / "SS2_Second_Term" / "Week03_Programming_Basics.md",
        ("SS2", "Second Term", 4): SAMPLES_DIR / "SS2_Second_Term" / "Week04_Control_Structures.md",
        ("SS2", "Second Term", 6): SAMPLES_DIR / "SS2_Second_Term" / "Week06_Data_Science_Basics.md",
        ("SS2", "Second Term", 8): SAMPLES_DIR / "SS2_Second_Term" / "Week08_Big_Data_Analytics.md",
        ("SS2", "Second Term", 9): SAMPLES_DIR / "SS2_Second_Term" / "Week09_Artificial_Intelligence.md",
        ("SS2", "Second Term", 10): SAMPLES_DIR / "SS2_Second_Term" / "Week10_Machine_Learning_Basics.md",
        ("SS1", "First Term", 3): SAMPLES_DIR / "SS1_First_Term_Week3_Number_Systems.md",
    }

    key = (class_level, term, week)
    if key in known_samples and known_samples[key].exists():
        content = known_samples[key].read_text(encoding="utf-8")
    else:
        content = f"""**Class:** {class_level}
**Term:** {term}
**Week:** {week}
**Topic:** {lesson['topic']}

**Official Content Breakdown**
{lesson['content']}

**Behavioral Learning Objectives**
By the end of this lesson, students should be able to:
1. Explain the main ideas of {lesson['topic']}.
2. Apply the key concepts in practical classroom activities.
3. Demonstrate understanding through examples and exercises.

**Key Concepts**
(Refer to official NERDC content: {lesson['content']})

**Step-by-Step Conceptual Explanation**
Teachers should expand this section using the official scheme content and classroom examples relevant to Nigerian students.

**Practical / Worked Example**
Prepare a concrete example based on: {lesson['content']}

**Class Activity**
Design a 10-15 minute activity aligned with the topic.

**End-of-Lesson Quick Test**
1. Define the main term related to this topic.
2. Give one real-life example.
3. State one importance of this topic.
4. True or False question.
5. Short application question.

**Assignment**
Give students a short practical or written task based on the topic.
"""

    return {
        "class_level": class_level,
        "term": term,
        "week": week,
        "topic": lesson["topic"],
        "official_content": lesson["content"],
        "is_exam_or_break": is_exam_or_break_week(lesson["topic"]),
        "lesson_note": content
    }


@app.get("/prompt/{class_level}/{term}/{week}")
async def get_generation_prompt(class_level: str, term: str, week: int):
    prompt = build_prompt(class_level, term, week)
    if not prompt:
        raise HTTPException(status_code=404, detail="No prompt available for this week")
    return {"prompt": prompt}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
