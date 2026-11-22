"""Regression checks for lesson lookup and the public HTTP surface."""
import asyncio
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi import HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from starlette.datastructures import UploadFile

from main import (
    SecurityHeadersMiddleware,
    analyze_handwriting_page,
    app,
    build_lesson_payload,
    get_lesson_note,
    get_topics,
    home,
)


def test_existing_and_new_web_routes_are_available():
    paths = app.openapi()["paths"]
    assert "/health" in paths
    assert "/topics" in paths
    assert "/lesson/{class_level}/{term}/{week}" in paths
    assert "/prompt/{class_level}/{term}/{week}" in paths
    assert "/export/lesson-pdf" in paths
    assert "/handwriting/calibration-sheet" in paths
    assert "/export/handwriting-pdf" in paths
    assert "/analyze/handwriting" in paths
    assert "/analyze/handwriting/confirm" in paths


def test_invalid_topic_filter_is_a_client_error():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(get_topics("SS4"))
    assert exc.value.status_code == 422


def test_prepared_lesson_is_identified_for_the_interface():
    result = asyncio.run(get_lesson_note("SS2", "Second Term", 2))
    assert result["content_status"] == "prepared"
    assert "Computer Programming II" in result["lesson_note"]


def test_curriculum_outline_is_not_mislabelled_as_a_prepared_note():
    result = asyncio.run(get_lesson_note("SS1", "First Term", 12))
    assert result["content_status"] == "outline"
    assert result["is_exam_or_break"] is True
    assert result["official_content"]


def test_hardware_note_is_assigned_to_the_curriculum_hardware_week():
    result = build_lesson_payload("SS1", "First Term", 4)
    assert result["content_status"] == "prepared"
    assert "Computer Hardware" in result["lesson_note"]

    midterm = build_lesson_payload("SS1", "First Term", 5)
    assert midterm["content_status"] == "outline"
    assert "Computer Hardware" not in midterm["lesson_note"]


def test_root_serves_compiled_frontend_when_build_exists():
    frontend_index = Path(__file__).resolve().parents[1] / "frontend" / "dist" / "index.html"
    response = asyncio.run(home())
    if frontend_index.is_file():
        assert isinstance(response, FileResponse)
        assert any(getattr(route, "path", None) == "/assets" for route in app.routes)
    else:
        assert isinstance(response, (HTMLResponse, str))
        body = response.body.decode() if isinstance(response, HTMLResponse) else response
        assert "Digital Technologies" in body or "Lesson" in body


def test_security_headers_are_added_without_overwriting_existing_headers():
    sent = []

    async def endpoint(scope, receive, send):
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"x-frame-options", b"SAMEORIGIN"), (b"x-existing", b"keep")],
        })
        await send({"type": "http.response.body", "body": b"ok"})

    async def capture(message):
        sent.append(message)

    middleware = SecurityHeadersMiddleware(endpoint)
    asyncio.run(middleware({"type": "http", "path": "/health"}, None, capture))
    headers = dict(sent[0]["headers"])
    assert headers[b"x-frame-options"] == b"SAMEORIGIN"
    assert headers[b"x-existing"] == b"keep"
    assert headers[b"x-content-type-options"] == b"nosniff"
    assert headers[b"referrer-policy"] == b"strict-origin-when-cross-origin"
    assert headers[b"permissions-policy"] == b"camera=(), microphone=(), geolocation=()"


def test_natural_page_route_reports_unconfigured_provider_without_guessing(monkeypatch):
    image = np.full((240, 640, 3), 255, dtype=np.uint8)
    cv2.putText(image, "Handwriting sample", (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 3)
    encoded = cv2.imencode(".png", image)[1].tobytes()
    monkeypatch.delenv("HTR_PROVIDER", raising=False)
    upload = UploadFile(file=BytesIO(encoded), filename="page.png")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(analyze_handwriting_page(upload))
    assert exc.value.status_code == 503
    assert "not enabled" in str(exc.value.detail)
