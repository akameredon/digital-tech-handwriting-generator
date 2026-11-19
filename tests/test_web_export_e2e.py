"""End-to-end test for the printable lesson-PDF download route."""
import asyncio
from pathlib import Path

from fastapi.responses import FileResponse


def test_printable_pdf_is_created_and_temporary_files_are_removed(monkeypatch, tmp_path):
    import main

    temp_dirs = []

    def make_temp_dir(prefix):
        temp_dir = tmp_path / f"lesson-pdf-{len(temp_dirs)}"
        temp_dir.mkdir()
        temp_dirs.append(temp_dir)
        return str(temp_dir)

    monkeypatch.setattr(main.tempfile, "mkdtemp", make_temp_dir)

    response = main.export_lesson_pdf(
        class_level="SS2",
        term="Second Term",
        week=2,
    )

    assert isinstance(response, FileResponse)
    assert response.media_type == "application/pdf"
    assert response.filename == "SS2_Second_Term_Week2_lesson.pdf"
    pdf_path = Path(response.path)
    assert pdf_path.is_file()
    assert pdf_path.stat().st_size > 500
    assert pdf_path.read_bytes().startswith(b"%PDF-")

    if response.background:
        asyncio.run(response.background())
    assert temp_dirs and not temp_dirs[0].exists()
