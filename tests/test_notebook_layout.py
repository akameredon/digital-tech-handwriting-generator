from pathlib import Path

from pypdf import PdfReader

from curriculum.lesson_generator import generate_complete_lesson
from renderer.notebook_layout import NotebookLayoutEngine, NotebookPDFRenderer


def test_layout_wraps_and_paginates_complete_lesson(tmp_path):
    markdown = generate_complete_lesson("SS2", "Second Term", 2)
    layout = NotebookLayoutEngine(chars_per_line=48).plan(markdown)
    assert layout.page_count >= 2
    assert all(len(page.lines) <= layout.lines_per_page for page in layout.pages)
    assert any(line.heading for page in layout.pages for line in page.lines)
    assert sum(len(page.lines) for page in layout.pages) >= 20


def test_pdf_has_one_page_per_layout_page_and_page_numbers(tmp_path):
    markdown = generate_complete_lesson("SS1", "First Term", 3)
    output = tmp_path / "lesson.pdf"
    layout = NotebookPDFRenderer(NotebookLayoutEngine(chars_per_line=48)).render(markdown, output)
    reader = PdfReader(str(output))
    assert output.exists() and len(reader.pages) == layout.page_count
    extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Number Systems" in extracted
    assert f"Page {layout.page_count}/{layout.page_count}" in extracted
