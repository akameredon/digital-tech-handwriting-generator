"""API-level checks for the optional calibration worksheet export."""
import asyncio
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.pagesizes import A4
from pypdf import PdfReader

from main import (
    MAX_HANDWRITING_REQUEST_BYTES,
    HandwritingUploadLimitMiddleware,
    download_calibration_sheet,
    export_handwriting_pdf,
)
from test_calibration_sheet import _make_calibration_image
from ingestion.calibration_sheet import CalibrationSheetError


def _encoded_scan(image: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return encoded.tobytes()


def test_declared_oversized_upload_is_rejected_before_the_application_runs():
    app_called = False

    async def app(scope, receive, send):
        nonlocal app_called
        app_called = True

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    messages = []
    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "path": "/export/handwriting-pdf",
        "headers": [(b"content-length", str(MAX_HANDWRITING_REQUEST_BYTES + 1).encode())],
    }
    asyncio.run(HandwritingUploadLimitMiddleware(app)(scope, receive, send))

    assert not app_called
    assert messages[0]["status"] == 413


def test_chunked_oversized_upload_is_stopped_at_the_asgi_boundary():
    async def app(scope, receive, send):
        await receive()
        await receive()

    chunks = [b"a" * MAX_HANDWRITING_REQUEST_BYTES, b"b"]

    async def receive():
        body = chunks.pop(0)
        return {"type": "http.request", "body": body, "more_body": bool(chunks)}

    messages = []
    async def send(message):
        messages.append(message)

    scope = {"type": "http", "path": "/export/handwriting-pdf", "headers": []}
    asyncio.run(HandwritingUploadLimitMiddleware(app)(scope, receive, send))

    assert messages[0]["status"] == 413


def test_optional_worksheet_download_is_pdf_and_temp_files_are_removed(tmp_path, monkeypatch):
    import main

    temp_dirs = []

    def make_temp_dir(prefix):
        path = tmp_path / f"calibration-{len(temp_dirs)}"
        path.mkdir()
        temp_dirs.append(path)
        return str(path)

    monkeypatch.setattr(main.tempfile, "mkdtemp", make_temp_dir)
    response = download_calibration_sheet()

    assert isinstance(response, FileResponse)
    assert response.filename == "digital-technologies-handwriting-calibration.pdf"
    assert Path(response.path).read_bytes().startswith(b"%PDF-")
    asyncio.run(response.background())
    assert temp_dirs and not temp_dirs[0].exists()


def test_export_rejects_arbitrary_notebook_image_with_specific_client_error():
    notebook = np.full((900, 700, 3), 255, dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", notebook)
    assert ok
    upload = UploadFile(file=BytesIO(encoded.tobytes()), filename="notebook.png")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(export_handwriting_pdf("SS2", "Second Term", 2, upload, confirm_labels=True))

    assert exc.value.status_code == 422
    assert "full landscape worksheet" in exc.value.detail or "generated calibration sheet" in exc.value.detail


@pytest.mark.parametrize("pillow_pixel_limit", [100, 300])
def test_decompression_bomb_images_return_actionable_validation_error(monkeypatch, pillow_pixel_limit):
    import ingestion.calibration_sheet as calibration_sheet

    image = np.full((20, 20, 3), 255, dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    monkeypatch.setattr(calibration_sheet.Image, "MAX_IMAGE_PIXELS", pillow_pixel_limit)

    with pytest.raises(CalibrationSheetError, match="safe size limit"):
        calibration_sheet.extract_calibration_glyphs(encoded.tobytes())


def _assert_a4_portrait_pdf(path: Path) -> PdfReader:
    reader = PdfReader(str(path))
    assert len(reader.pages) >= 1
    page = reader.pages[0]
    assert abs(float(page.mediabox.width) - A4[0]) < 1.0
    assert abs(float(page.mediabox.height) - A4[1]) < 1.0
    extracted = "\n".join(item.extract_text() or "" for item in reader.pages)
    assert extracted.strip()
    assert "Week 2" in extracted
    return reader


def _has_embedded_truetype_font(reader: PdfReader) -> bool:
    for page in reader.pages:
        resources = page.get("/Resources")
        if not resources:
            continue
        fonts = resources.get_object().get("/Font")
        if not fonts:
            continue
        for font_ref in fonts.get_object().values():
            font = font_ref.get_object()
            descriptor = font.get("/FontDescriptor")
            if descriptor and descriptor.get_object().get("/FontFile2"):
                return True
            for descendant_ref in font.get("/DescendantFonts", []):
                descendant = descendant_ref.get_object()
                descendant_descriptor = descendant.get("/FontDescriptor")
                if descendant_descriptor and descendant_descriptor.get_object().get("/FontFile2"):
                    return True
    return False


def test_export_requires_teacher_to_confirm_worksheet_labels():
    upload = UploadFile(file=BytesIO(_encoded_scan(_make_calibration_image())), filename="worksheet.png")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(export_handwriting_pdf("SS2", "Second Term", 2, upload, confirm_labels=False))

    assert exc.value.status_code == 422
    assert "matches its printed worksheet label" in exc.value.detail


def test_optional_worksheet_export_returns_pdf_with_coverage_and_fallback_headers():
    upload = UploadFile(file=BytesIO(_encoded_scan(_make_calibration_image())), filename="worksheet.png")
    fonts_before = set(pdfmetrics._fonts)
    faces_before = set(pdfmetrics._dynFaceNames)
    response = asyncio.run(export_handwriting_pdf("SS2", "Second Term", 2, upload, confirm_labels=True))

    assert isinstance(response, FileResponse)
    assert response.media_type == "application/pdf"
    assert response.filename == "SS2_Second_Term_Week2_handwriting_style.pdf"
    assert response.headers["x-handwriting-coverage"] == "77/77"
    assert response.headers["x-handwriting-missing-count"] == "0"
    assert response.headers["x-handwriting-fallback"] == "Helvetica"
    reader = _assert_a4_portrait_pdf(Path(response.path))
    assert reader.metadata.title and "SS2 Second Term Week 2" in reader.metadata.title
    assert _has_embedded_truetype_font(reader), "the generated teacher font must be embedded in the PDF"
    assert set(pdfmetrics._fonts) == fonts_before
    assert set(pdfmetrics._dynFaceNames) == faces_before
    asyncio.run(response.background())
