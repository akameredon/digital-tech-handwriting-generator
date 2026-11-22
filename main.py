"""Digital Technologies lesson-note API and printable PDF service."""

import asyncio
import json
import logging
import os
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
from ingestion.open_handwriting import HandwritingIntakeError, OpenHandwritingIntake, RecognitionUnavailable
from model.font_compiler import FontCompilationError, FontCompiler
from model.glyph_alignment_pipeline import (
    align_document_glyphs,
    confirm_document_glyphs,
    learn_writer_profile,
)
from model.htr import HTRPipeline
from model.htr_providers import (
    HTRProviderConfigurationError,
    kraken_from_environment,
    trocr_from_environment,
)
from model.profile_management import ManagedWriterProfile, WriterProfileStore
from renderer.pdf_exporter import ClassmatePDFExporter

logger = logging.getLogger(__name__)
MAX_HANDWRITING_REQUEST_BYTES = MAX_IMAGE_BYTES + 256 * 1024
_natural_htr_provider = None


class RequestBodyTooLarge(Exception):
    """Raised when a request exceeds the upload endpoint's body limit."""


class HandwritingUploadLimitMiddleware:
    """Limit the full multipart body before Starlette spools an oversized upload."""

    def __init__(self, app):
        self.app = app
        self.active_uploads = asyncio.Semaphore(2)

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or scope.get("path") not in {"/export/handwriting-pdf", "/analyze/handwriting"}:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError:
                response = JSONResponse({"detail": "Invalid upload content length."}, status_code=400)
                await response(scope, receive, send)
                return
            if declared_length > MAX_HANDWRITING_REQUEST_BYTES:
                response = JSONResponse(
                    {"detail": "The upload request is too large. Keep the worksheet image under 12 MB."},
                    status_code=413,
                )
                await response(scope, receive, send)
                return

        received_bytes = 0

        async def limited_receive():
            nonlocal received_bytes
            message = await receive()
            if message.get("type") == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > MAX_HANDWRITING_REQUEST_BYTES:
                    raise RequestBodyTooLarge
            return message

        try:
            async with self.active_uploads:
                await self.app(scope, limited_receive, send)
        except RequestBodyTooLarge:
            response = JSONResponse(
                {"detail": "The upload request is too large. Keep the worksheet image under 12 MB."},
                status_code=413,
            )
            await response(scope, receive, send)


class SecurityHeadersMiddleware:
    """Add browser-safe defaults without requiring a reverse proxy."""

    HEADERS = (
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"referrer-policy", b"strict-origin-when-cross-origin"),
        (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
    )

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        async def secured_send(message):
            if message.get("type") == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}
                headers.extend((name, value) for name, value in self.HEADERS if name not in present)
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, secured_send)


app = FastAPI(
    title="Digital Technologies Lesson Note Generator",
    description="NERDC 2025 aligned lesson notes for SS1-SS3 Digital Technologies",
    version="1.1.2"
)
app.add_middleware(HandwritingUploadLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

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


def _configured_natural_htr_provider():
    """Return the explicitly configured local provider, without guessing.

    Model initialization is lazy and happens only when the natural-page route
    is used. The base application remains usable without the optional ML extra.
    """
    global _natural_htr_provider
    provider_name = os.getenv("HTR_PROVIDER", "").lower()
    if provider_name not in {"trocr", "kraken"}:
        raise RecognitionUnavailable(
            "Natural-page handwriting recognition is not enabled on this server. "
            "Set HTR_PROVIDER=trocr or HTR_PROVIDER=kraken after provisioning an optional local model."
        )
    if _natural_htr_provider is None:
        _natural_htr_provider = (
            kraken_from_environment() if provider_name == "kraken" else trocr_from_environment()
        )
    return _natural_htr_provider


def _analyze_natural_handwriting(image_bytes: bytes):
    """Analyze one page and retain all HTR/alignment evidence for review."""
    temp_dir = Path(tempfile.mkdtemp(prefix="dt-natural-handwriting-"))
    image_path = temp_dir / "page.jpg"
    try:
        image_path.write_bytes(image_bytes)
        analysis = OpenHandwritingIntake().analyze(image_path)
        provider = _configured_natural_htr_provider()
        recognition = HTRPipeline(provider).recognize(analysis)
        alignment = align_document_glyphs(analysis, recognition)
        return {
            "analysis": analysis.public_dict(),
            "recognition": recognition.public_dict(),
            "glyph_alignment": alignment.public_dict(),
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@app.post("/analyze/handwriting")
async def analyze_handwriting_page(page: UploadFile = File(...)):
    """Analyze a natural page without compiling any unconfirmed glyphs."""
    request_id = uuid4().hex[:12]
    temp_bytes = None
    try:
        temp_bytes = await page.read(MAX_IMAGE_BYTES + 1)
        if len(temp_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="The handwriting page must be smaller than 12 MB.")
        if not temp_bytes:
            raise HTTPException(status_code=422, detail="Upload a JPG or PNG handwriting page.")
        return await run_in_threadpool(_analyze_natural_handwriting, temp_bytes)
    except HTTPException:
        raise
    except HandwritingIntakeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RecognitionUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except HTRProviderConfigurationError as exc:
        logger.exception("Natural handwriting provider unavailable request_id=%s", request_id)
        raise HTTPException(
            status_code=503,
            detail=f"Natural handwriting recognition is not ready. Reference: {request_id}",
        ) from exc
    except Exception as exc:
        logger.exception("Natural handwriting analysis failed request_id=%s", request_id)
        raise HTTPException(
            status_code=500,
            detail=f"The handwriting page could not be analyzed. Reference: {request_id}",
        ) from exc


@app.post("/analyze/handwriting/confirm")
async def confirm_handwriting_page(
    page: UploadFile = File(...),
    confirmations: str = Form(...),
    writer_name: str = Form(...),
):
    """Persist only explicit browser confirmations as writer-profile evidence."""
    try:
        parsed = json.loads(confirmations)
    except (TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="confirmations must be a JSON object.") from exc
    if not isinstance(parsed, dict) or not parsed or not writer_name.strip():
        raise HTTPException(status_code=422, detail="Provide a writer name and at least one confirmation.")
    if not all(isinstance(key, str) and isinstance(value, str) for key, value in parsed.items()):
        raise HTTPException(status_code=422, detail="Confirmation keys and labels must be strings.")

    image_bytes = await page.read(MAX_IMAGE_BYTES + 1)
    if len(image_bytes) > MAX_IMAGE_BYTES or not image_bytes:
        raise HTTPException(status_code=422, detail="Upload a non-empty handwriting page smaller than 12 MB.")
    temp_dir = Path(tempfile.mkdtemp(prefix="dt-confirm-handwriting-"))
    try:
        image_path = temp_dir / "page.jpg"
        image_path.write_bytes(image_bytes)
        page_analysis = OpenHandwritingIntake().analyze(image_path)
        recognition = HTRPipeline(_configured_natural_htr_provider()).recognize(page_analysis)
        alignment = align_document_glyphs(page_analysis, recognition)
        confirmed = confirm_document_glyphs(
            alignment,
            parsed,
            source_width=page_analysis.width,
            source_height=page_analysis.height,
        )
    except (HandwritingIntakeError, RecognitionUnavailable, HTRProviderConfigurationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    learned = learn_writer_profile(confirmed, writer_name=writer_name.strip())
    store = WriterProfileStore(os.getenv("WRITER_PROFILE_DIR", "data/writer_profiles"))
    try:
        managed = store.load(writer_name.strip())
    except FileNotFoundError:
        managed = ManagedWriterProfile(learned.profile)
        managed.evidence = dict(learned.evidence)
    else:
        store.merge_learning(managed, learned)
    destination = store.save(managed)
    return {
        "profile": managed.public_dict(),
        "path": str(destination),
        "confirmed_count": len(confirmed.observations),
        "learning": learned.public_dict(),
    }


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
