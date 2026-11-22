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

from main import (
    MAX_HANDWRITING_REQUEST_BYTES,
    HandwritingUploadLimitMiddleware,
    download_calibration_sheet,
    export_handwriting_pdf,
)
from test_calibration_sheet import _make_calibration_image


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
    assert Path(response.path).read_bytes().startswith(b"%PDF-")
    assert set(pdfmetrics._fonts) == fonts_before
    assert set(pdfmetrics._dynFaceNames) == faces_before
    asyncio.run(response.background())
