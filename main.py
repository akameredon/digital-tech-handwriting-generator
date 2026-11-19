"""Digital Technologies lesson-note API and printable PDF service."""

import logging
from pathlib import Path
import shutil
import tempfile
from typing import Optional

import uvicorn
from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask

from curriculum.nerdc_schemes import get_lesson, list_all_topics
from curriculum.prompt_engine import build_prompt
from curriculum.sample_notes import get_prepared_lesson
from curriculum.validator import is_exam_or_break_week
from renderer.pdf_exporter import ClassmatePDFExporter

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Digital Technologies Lesson Note Generator",
    description="NERDC 2025 aligned lesson notes for SS1-SS3 Digital Technologies",
    version="1.1.2"
)

ROOT_DIR = Path(__file__).parent
SAMPLES_DIR = ROOT_DIR / "samples"
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"
if (FRONTEND_DIST / "assets").is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=str(FRONTEND_DIST / "assets")),
        name="frontend-assets"
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "Digital Technologies Lesson Note Generator", "version": "1.1.2"}


@app.get("/", response_class=HTMLResponse)
async def home():
    frontend_index = FRONTEND_DIST / "index.html"
    if frontend_index.is_file():
        return FileResponse(frontend_index)

    weeks = "".join(f'<option value="{i}">{i}</option>' for i in range(1, 14))
    return f"""
    <html>
    <head>
        <title>Digital Technologies Lesson Note Generator</title>
        <style>
            body{{font-family:system-ui,sans-serif;max-width:920px;margin:40px auto;padding:0 20px;line-height:1.5}}
            h1{{color:#1a237e}} h2{{color:#0d47a1;margin-top:1.8em}}
            .card{{background:#f5f5f5;padding:18px;border-radius:10px;margin:14px 0}}
            a{{color:#0d47a1}} code{{background:#e3f2fd;padding:2px 6px;border-radius:4px}}
            label{{display:block;margin:10px 0 4px;font-weight:600}}
            select,button{{padding:8px 12px;font-size:15px;border-radius:6px;border:1px solid #90caf9}}
            button{{background:#1a237e;color:white;border:none;cursor:pointer;margin-top:12px}}
            button:hover{{background:#0d47a1}}
        </style>
    </head>
    <body>
        <h1>Digital Technologies Lesson Note Generator</h1>
        <p>NERDC 2025 • SS1 – SS3 • v1.1.2</p>

        <div class="card">
            <h2>Get a Lesson Note</h2>
            <form action="/lesson-form" method="get">
                <label>Class</label>
                <select name="class_level">
                    <option value="SS1">SS1</option>
                    <option value="SS2" selected>SS2</option>
                    <option value="SS3">SS3</option>
                </select>
                <label>Term</label>
                <select name="term">
                    <option>First Term</option>
                    <option selected>Second Term</option>
                    <option>Third Term</option>
                </select>
                <label>Week</label>
                <select name="week">{weeks}</select>
                <br>
                <button type="submit">Generate Lesson Note</button>
            </form>
        </div>

        <div class="card">
            <h2>Quick Links</h2>
            <ul>
                <li><a href="/docs">API Documentation (Swagger)</a></li>
                <li><a href="/topics">List all topics</a></li>
                <li><a href="/health">Health Check</a></li>
            </ul>
        </div>
    </body>
    </html>
    """


@app.get("/lesson-form")
async def lesson_form(class_level: str = "SS2", term: str = "Second Term", week: int = 2):
    term_enc = term.replace(" ", "%20")
    return RedirectResponse(url=f"/lesson/{class_level}/{term_enc}/{week}")


@app.get("/topics")
async def get_topics(class_level: Optional[str] = None):
    if class_level is not None and class_level not in {"SS1", "SS2", "SS3"}:
        raise HTTPException(status_code=422, detail="class_level must be SS1, SS2, or SS3")
    return list_all_topics(class_level)


def build_lesson_payload(class_level: str, term: str, week: int):
    lesson = get_lesson(class_level, term, week)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found in official NERDC scheme")

    lesson_content = get_prepared_lesson(class_level, term, week, SAMPLES_DIR)
    is_prepared = lesson_content is not None
    if not is_prepared:
        lesson_content = f"""**Class:** {class_level}
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
        "lesson_note": lesson_content,
        "content_status": "prepared" if is_prepared else "outline"
    }


@app.get("/lesson/{class_level}/{term}/{week}")
async def get_lesson_note(class_level: str, term: str, week: int):
    return build_lesson_payload(class_level, term, week)


@app.get("/prompt/{class_level}/{term}/{week}")
async def get_generation_prompt(class_level: str, term: str, week: int):
    prompt = build_prompt(class_level, term, week)
    if not prompt:
        raise HTTPException(status_code=404, detail="No prompt available for this week")
    return {"prompt": prompt}


@app.post("/export/lesson-pdf")
def export_lesson_pdf(
    class_level: str = Form(...),
    term: str = Form(...),
    week: int = Form(...)
):
    """Create a printable ruled PDF without claiming to reproduce handwriting."""
    payload = build_lesson_payload(class_level, term, week)
    temp_dir = Path(tempfile.mkdtemp(prefix="dt-lesson-pdf-"))
    try:
        pdf_path = ClassmatePDFExporter().export_lesson(
            payload["lesson_note"],
            temp_dir / "lesson_note.pdf",
            title=f"{class_level} {term} Week {week}",
        )
        filename = f"{class_level}_{term.replace(' ', '_')}_Week{week}_lesson.pdf"
        return FileResponse(
            path=str(pdf_path),
            media_type="application/pdf",
            filename=filename,
            background=BackgroundTask(shutil.rmtree, temp_dir, ignore_errors=True),
        )
    except Exception:
        logger.exception("Printable lesson PDF export failed")
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail="The printable PDF could not be created. Please try again.")


@app.post("/export/handwriting-pdf")
async def export_handwriting_pdf():
    """Keep the legacy endpoint but refuse to fabricate handwriting without HTR."""
    raise HTTPException(
        status_code=503,
        detail=(
            "Handwriting-to-font export is disabled because this service has no integrated "
            "handwriting recognizer or verified text-to-glyph alignment. No handwriting PDF was generated. "
            "Use the printable lesson PDF instead."
        ),
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
