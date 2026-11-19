"""Regression checks for the additive teacher-facing web surface."""

import asyncio
from pathlib import Path

from fastapi.responses import FileResponse, HTMLResponse

from main import app, get_lesson_note, home


def test_existing_web_routes_remain_available():
    paths = app.openapi()["paths"]
    assert "/health" in paths
    assert "/topics" in paths
    assert "/lesson/{class_level}/{term}/{week}" in paths
    assert "/prompt/{class_level}/{term}/{week}" in paths


def test_handwriting_export_route_is_additive():
    paths = app.openapi()["paths"]
    assert "/export/handwriting-pdf" in paths
    assert "post" in paths["/export/handwriting-pdf"]


def test_prepared_lesson_is_identified_for_the_interface():
    result = asyncio.run(get_lesson_note("SS2", "Second Term", 2))
    assert result["content_status"] == "prepared"
    assert result["topic"]


def test_curriculum_outline_is_not_mislabelled_as_a_prepared_note():
    # Exam / break weeks must not be sold as full prepared instructional notes
    result = asyncio.run(get_lesson_note("SS1", "First Term", 12))
    assert result["content_status"] in ("outline", "exam_or_break")
    assert result["is_exam_or_break"] is True
    assert result["official_content"]


def test_root_serves_compiled_frontend_when_build_exists():
    frontend_index = Path(__file__).resolve().parents[1] / "frontend" / "dist" / "index.html"
    response = asyncio.run(home())
    if frontend_index.is_file():
        assert isinstance(response, FileResponse)
        assert any(getattr(route, "path", None) == "/assets" for route in app.routes)
    else:
        # Direct coroutine call returns HTML string body or HTMLResponse depending on FastAPI wrapping
        assert isinstance(response, (HTMLResponse, str))
        body = response.body.decode() if isinstance(response, HTMLResponse) else response
        assert "Digital Technologies" in body or "Lesson" in body


def test_handwriting_export_wraps_existing_pipeline_and_cleans_temp_files(monkeypatch, tmp_path):
    from io import BytesIO

    import main

    from PIL import Image

    image_buffer = BytesIO()
    Image.new("RGB", (120, 120), "white").save(image_buffer, format="PNG")

    class FakeUpload:
        content_type = "image/png"

        def __init__(self):
            self.file = BytesIO(image_buffer.getvalue())

        def close(self):
            self.file.close()

    class FakePreprocessor:
        def process(self, image_path, expected_chars=None, save_debug=False):
            return [{"label": chr(65 + index), "image": None} for index in range(20)]

    class FakeFontCompiler:
        def compile(self, glyphs, output_path, family_name):
            assert len(glyphs) == 20
            assert family_name.startswith("TeacherHandwriting_")
            output_path.write_bytes(b"fake-font")
            return output_path

    class FakePdfExporter:
        def __init__(self, font_path, font_name):
            assert Path(font_path).is_file()
            assert font_name.startswith("TeacherHandwriting_")

        def export_lesson(self, text, output_path, title):
            assert text
            output_path.write_bytes(b"%PDF-fake")
            return output_path

    temp_dir = tmp_path / "handwriting-run"

    def make_temp_dir(prefix):
        temp_dir.mkdir()
        return str(temp_dir)

    monkeypatch.setattr(main.tempfile, "mkdtemp", make_temp_dir)
    monkeypatch.setattr(main, "HandwritingPreprocessor", FakePreprocessor)
    monkeypatch.setattr(main, "FontCompiler", FakeFontCompiler)
    monkeypatch.setattr(main, "ClassmatePDFExporter", FakePdfExporter)

    response = main.export_handwriting_pdf(
        class_level="SS2",
        term="Second Term",
        week=2,
        sample=FakeUpload()
    )

    assert isinstance(response, FileResponse)
    assert response.media_type == "application/pdf"
    assert Path(response.path).read_bytes().startswith(b"%PDF")

    if response.background:
        asyncio.run(response.background())
    assert not temp_dir.exists()
