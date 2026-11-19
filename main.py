"""
Digital Technologies Handwriting Lesson Note Generator
FastAPI entry point - production ready for teacher use.
"""

from io import BytesIO
from pathlib import Path
import shutil
import tempfile
import threading
import uuid
from typing import Optional

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from starlette.background import BackgroundTask

from curriculum.nerdc_schemes import get_lesson, list_all_topics
from curriculum.prompt_engine import build_prompt
from curriculum.validator import is_exam_or_break_week
from ingestion.preprocessor import DEFAULT_SAMPLE_ORDER, HandwritingPreprocessor, HandwritingSampleError
from model.font_compiler import FontCompiler, FontCompilationError
from renderer.pdf_exporter import ClassmatePDFExporter

app = FastAPI(
    title="Digital Technologies Lesson Note Generator",
    description="NERDC 2025 aligned lesson notes for SS1-SS3 Digital Technologies",
    version="1.1.1"
)

ROOT_DIR = Path(__file__).parent
SAMPLES_DIR = ROOT_DIR / "samples"
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"
MAX_SAMPLE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
PROCESSING_SLOTS = threading.BoundedSemaphore(2)
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
}

if (FRONTEND_DIST / "assets").is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=str(FRONTEND_DIST / "assets")),
        name="frontend-assets"
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "Digital Technologies Lesson Note Generator", "version": "1.1.1"}


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
        <p>NERDC 2025 • SS1 – SS3 • v1.1.1</p>

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
    return list_all_topics(class_level)


def build_lesson_payload(class_level: str, term: str, week: int):
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
    prepared_path = known_samples.get(key)
    is_prepared = bool(prepared_path and prepared_path.is_file())
    if is_prepared:
        lesson_content = prepared_path.read_text(encoding="utf-8")
    else:
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


@app.post("/export/handwriting-pdf")
def export_handwriting_pdf(
    class_level: str = Form(...),
    term: str = Form(...),
    week: int = Form(...),
    sample: UploadFile = File(...)
):
    """Handwriting photo → font → notebook PDF. Accepts ordinary teacher samples."""
    lesson = get_lesson(class_level, term, week)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found in the curriculum.")

    if sample.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="Please upload a JPG or PNG image.")

    file_bytes = sample.file.read(MAX_SAMPLE_BYTES + 1)
    if not file_bytes:
        raise HTTPException(status_code=400, detail="The selected image is empty.")
    if len(file_bytes) > MAX_SAMPLE_BYTES:
        raise HTTPException(status_code=413, detail="The image is larger than 8 MB. Choose a smaller image.")

    try:
        with Image.open(BytesIO(file_bytes)) as image:
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise HTTPException(status_code=413, detail="This image is too large to process. Choose a lower-resolution photo.")
            image.verify()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=422, detail="We couldn't read this image. Choose a clear JPG or PNG file.")

    if not PROCESSING_SLOTS.acquire(blocking=False):
        raise HTTPException(status_code=503, detail="The handwriting service is busy. Please try again in a moment.")

    temp_dir = None
    try:
        temp_dir = Path(tempfile.mkdtemp(prefix="dt-handwriting-"))
        image_path = temp_dir / ALLOWED_IMAGE_TYPES[sample.content_type]
        image_path.write_bytes(file_bytes)

        preprocessor = HandwritingPreprocessor()
        glyphs = preprocessor.process(
            image_path,
            expected_chars=DEFAULT_SAMPLE_ORDER,
            save_debug=False
        )
        if len(glyphs) < 8:
            raise HTTPException(
                status_code=422,
                detail="We found too few clear characters. Write letters clearly with a little space between them and try again."
            )

        unique_font_name = f"TeacherHandwriting_{uuid.uuid4().hex[:12]}"
        font_path = FontCompiler().compile(
            glyphs,
            temp_dir / "teacher_handwriting.ttf",
            family_name=unique_font_name
        )
        if not font_path or not Path(font_path).is_file():
            raise HTTPException(
                status_code=422,
                detail="We could not build a font from this photo. Try a clearer image with dark ink on light paper."
            )

        note_text = build_lesson_payload(class_level, term, week)["lesson_note"]
        pdf_path = ClassmatePDFExporter(
            font_path=str(font_path),
            font_name=unique_font_name
        ).export_lesson(
            note_text,
            temp_dir / "lesson_note.pdf",
            title=f"{class_level} {term} Week {week}"
        )
        if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
            raise HTTPException(status_code=500, detail="The PDF could not be created. Please try again.")

        filename = f"{class_level}_{term.replace(' ', '_')}_Week{week}_handwriting.pdf"
        return FileResponse(
            path=str(pdf_path),
            media_type="application/pdf",
            filename=filename,
            background=BackgroundTask(shutil.rmtree, temp_dir, ignore_errors=True)
        )
    except HTTPException:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    except (HandwritingSampleError, FontCompilationError) as exc:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(
            status_code=422,
            detail="We could not read enough handwriting in this photo. Try a clearer image with dark ink on light paper."
        )
    finally:
        sample.file.close()
        PROCESSING_SLOTS.release()


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
