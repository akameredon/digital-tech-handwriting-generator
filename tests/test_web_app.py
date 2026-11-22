"""Regression checks for lesson lookup and the public HTTP surface."""
import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from main import app, build_lesson_payload, get_lesson_note, get_topics, home


def test_existing_and_new_web_routes_are_available():
    paths = app.openapi()["paths"]
    assert "/health" in paths
    assert "/topics" in paths
    assert "/lesson/{class_level}/{term}/{week}" in paths
    assert "/prompt/{class_level}/{term}/{week}" in paths
    assert "/export/lesson-pdf" in paths
    assert "/handwriting/calibration-sheet" in paths
    assert "/export/handwriting-pdf" in paths


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
