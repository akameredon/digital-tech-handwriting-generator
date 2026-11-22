"""Digital Technologies lesson-note API and printable PDF service."""

import asyncio
import logging
from pathlib import Path
import shutil
import tempfile
from typing import Optional
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask

from curriculum.nerdc_schemes import get_lesson, list_all_topics
from curriculum.prompt_engine import build_prompt
from curriculum.sample_notes import get_prepared_lesson
from curriculum.validator import is_exam_or_break_week
from ingestion.calibration_sheet import (
    MAX_IMAGE_BYTES,
    CalibrationSheetError,
    extract_calibration_glyphs,
    write_calibration_sheet,
)
from ingestion.preprocessor import DEFAULT_SAMPLE_ROWS
from ingestion.open_handwriting import OpenHandwritingIntake, HandwritingIntakeError, MAX_NATURAL_PAGE_BYTES
from model.font_compiler import FontCompilationError, FontCompiler
from renderer.pdf_exporter import ClassmatePDFExporter

logger = logging.getLogger(__name__)
MAX_HANDWRITING_REQUEST_BYTES = MAX_IMAGE_BYTES + 256 * 1024
MAX_NATURAL_PAGE_REQUEST_BYTES = MAX_NATURAL_PAGE_BYTES + 256 * 1024


class RequestBodyTooLarge(Exception):
    """Raised when a request exceeds the upload endpoint's body limit."""


class HandwritingUploadLimitMiddleware:
    """Limit the full multipart body before Starlette spools an oversized upload."""

    def __init__(self, app):
        self.app = app
        self.active_uploads = asyncio.Semaphore(2)

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or scope.get("path") not in {
            "/export/handwriting-pdf", "/handwriting/analyze"
        }:
            await self.app(scope, receive, send)
            return
        request_limit = MAX_HANDWRITING_REQUEST_BYTES if scope.get("path") == "/export/handwriting-pdf" else MAX_NATURAL_PAGE_REQUEST_BYTES

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError:
                response = JSONResponse({"detail": "Invalid upload content length."}, status_code=400)
                await response(scope, receive, send)
                return
            if declared_length > request_limit:
                message = "The upload request is too large. Keep the worksheet image under 12 MB." if scope.get("path") == "/export/handwriting-pdf" else "The image upload request is too large. Keep the page image under 12 MB."
                response = JSONResponse({"detail": message}, status_code=413)
                await response(scope, receive, send)
                return

        received_bytes = 0

        async def limited_receive():
            nonlocal received_bytes
            message = await receive()
            if message.get("type") == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > request_limit:
                    raise RequestBodyTooLarge
            return message

        try:
            async with self.active_uploads:
                await self.app(scope, limited_receive, send)
        except RequestBodyTooLarge:
            message = "The upload request is too large. Keep the worksheet image under 12 MB." if scope.get("path") == "/export/handwriting-pdf" else "The image upload request is too large. Keep the page image under 12 MB."
            response = JSONResponse({"detail": message}, status_code=413)
            await response(scope, receive, send)

app = FastAPI(
    title="Digital Technologies Lesson Note Generator",
    description="NERDC 2025 aligned lesson notes for SS1-SS3 Digital Technologies",
    version="1.1.2"
)
app.add_middleware(HandwritingUploadLimitMiddleware)

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




@app.post("/handwriting/analyze")
async def analyze_natural_handwriting_page(page: UploadFile = File(...)):
    """Inspect a natural notebook page; this endpoint does not claim HTR recognition."""
    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if page.content_type not in allowed_types:
        raise HTTPException(status_code=415, detail="Upload a JPG, PNG or WebP image.")
    try:
        image_bytes = await page.read(12 * 1024 * 1024 + 1)
        analysis = await run_in_threadpool(
            OpenHandwritingIntake().analyze_bytes, image_bytes
        )
        return JSONResponse(
            content={
                "status": "analyzed",
                "recognition_status": "not_configured",
                "source_retention": "not_stored",
                "message": "The page was analyzed and handwriting lines were detected. Text recognition is not yet configured.",
                "analysis": analysis.public_dict(),
            },
            headers={"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache"},
        )
    except HandwritingIntakeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await page.close()


@app.get("/handwriting/calibration-sheet")
def download_calibration_sheet():
    """Download the optional fixed-layout worksheet used only for known-cell labels."""
    temp_dir = Path(tempfile.mkdtemp(prefix="dt-calibration-sheet-"))
    try:
        sheet_path = write_calibration_sheet(temp_dir / "handwriting_calibration.pdf")
        return FileResponse(
            path=str(sheet_path),
            media_type="application/pdf",
            filename="digital-technologies-handwriting-calibration.pdf",
            background=BackgroundTask(shutil.rmtree, temp_dir, ignore_errors=True),
        )
    except Exception:
        logger.exception("Handwriting calibration sheet could not be created")
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail="The optional calibration sheet could not be created.")


def _create_handwriting_pdf(payload, image_bytes: bytes, temp_dir: Path, request_id: str):
    glyphs, _missing_from_scan = extract_calibration_glyphs(image_bytes)
    font_path = FontCompiler().compile(
        glyphs,
        temp_dir / "teacher_handwriting.ttf",
        family_name=f"TeacherHandwriting{request_id}",
        style_name="Regular",
    )
    font_name = f"TeacherHandwriting_{request_id}"
    exporter = ClassmatePDFExporter(font_path=str(font_path), font_name=font_name)
    try:
        pdf_path = exporter.export_lesson(
            payload["lesson_note"],
            temp_dir / "handwriting_lesson.pdf",
            title=f"{payload['class_level']} {payload['term']} Week {payload['week']} — handwriting-style",
        )
        expected_chars = set("".join(DEFAULT_SAMPLE_ROWS))
        covered = len(exporter.custom_supported & expected_chars)
        missing_count = len(expected_chars - exporter.custom_supported)
        return pdf_path, covered, len(expected_chars), missing_count
    finally:
        exporter.release_temporary_font()


@app.post("/export/handwriting-pdf")
async def export_handwriting_pdf(
    class_level: str = Form(...),
    term: str = Form(...),
    week: int = Form(...),
    calibration_scan: UploadFile = File(...),
    confirm_labels: bool = Form(False),
):
    """Create a partial handwritten-style PDF from the optional labeled worksheet only."""
    payload = build_lesson_payload(class_level, term, week)
    if not confirm_labels:
        raise HTTPException(
            status_code=422,
            detail="Confirm that each handwritten character matches its printed worksheet label before exporting.",
        )

    request_id = uuid4().hex[:12]
    temp_dir = None
    try:
        image_bytes = await calibration_scan.read(MAX_IMAGE_BYTES + 1)
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=422, detail="The scan must be smaller than 12 MB.")
        temp_dir = Path(tempfile.mkdtemp(prefix="dt-handwriting-pdf-"))
        pdf_path, covered, total, missing_count = await run_in_threadpool(
            _create_handwriting_pdf, payload, image_bytes, temp_dir, request_id
        )
        return FileResponse(
            path=str(pdf_path),
            media_type="application/pdf",
            filename=f"{class_level}_{term.replace(' ', '_')}_Week{week}_handwriting_style.pdf",
            headers={
                "X-Handwriting-Coverage": f"{covered}/{total}",
                "X-Handwriting-Missing-Count": str(missing_count),
                "X-Handwriting-Fallback": "Helvetica",
            },
            background=BackgroundTask(shutil.rmtree, temp_dir, ignore_errors=True),
        )
    except HTTPException:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    except (CalibrationSheetError, FontCompilationError) as exc:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        logger.exception("Handwriting-style PDF export failed request_id=%s", request_id)
        raise HTTPException(
            status_code=500,
            detail=f"The PDF could not be created. Reference: {request_id}",
        ) from exc


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
