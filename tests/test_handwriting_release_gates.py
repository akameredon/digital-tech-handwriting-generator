"""Tests for open handwriting acceptance (real teacher photos)."""
from pathlib import Path
import sys
import numpy as np
import pytest
from fontTools.ttLib import TTFont as FontToolsTTFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ingestion.preprocessor import HandwritingPreprocessor, DEFAULT_SAMPLE_ORDER
from model.font_compiler import FontCompiler, FontCompilationError
from renderer.pdf_exporter import ClassmatePDFExporter


def synthetic_blobs(n=40):
    image = np.zeros((400, 900), dtype=np.uint8)
    for i in range(n):
        row, col = divmod(i, 13)
        x, y = 20 + col * 60, 20 + row * 55
        image[y:y+28, x:x+18] = 255
    return image


def test_open_extraction_does_not_require_exact_row_counts():
    processor = HandwritingPreprocessor()
    # Wrong row geometry must still return glyphs, not raise template errors
    glyphs = processor.extract_glyphs(synthetic_blobs(35), DEFAULT_SAMPLE_ORDER)
    assert len(glyphs) >= 8


def test_font_compiler_accepts_partial_glyph_set(tmp_path):
    glyphs = [
        {"label": char, "image": np.ones((20, 12), dtype=np.uint8) * 255, "row": 1}
        for char in "ABCDEFGH"
    ]
    path = FontCompiler().compile(glyphs, tmp_path / "partial.ttf")
    assert path.is_file() and path.stat().st_size > 500
    with FontToolsTTFont(path) as font:
        cmap = font.getBestCmap()
    assert {chr(codepoint) for codepoint in cmap} == set("ABCDEFGH")

    exporter = ClassmatePDFExporter(font_path=str(path))
    assert exporter._font_for("A") == "TeacherHandwriting"
    assert exporter._font_for("Z") == "Helvetica"
    assert exporter._font_for("?") == "Helvetica"


def test_font_compiler_rejects_a_partial_set_with_fewer_than_eight_valid_glyphs(tmp_path):
    glyphs = [
        {"label": char, "image": np.ones((20, 12), dtype=np.uint8) * 255, "row": 1}
        for char in "ABCDEFG"
    ]
    glyphs.append({"label": "H", "image": np.zeros((20, 12), dtype=np.uint8), "row": 1})
    with pytest.raises(FontCompilationError, match="Only 7 clear characters"):
        FontCompiler().compile(glyphs, tmp_path / "too-few.ttf")


def test_font_compiler_rejects_almost_empty(tmp_path):
    with pytest.raises(FontCompilationError):
        FontCompiler().compile(
            [{"label": "A", "image": np.ones((20, 12), dtype=np.uint8) * 255}],
            tmp_path / "empty.ttf",
        )


def test_pdf_export_creates_nonempty_document(tmp_path):
    exporter = ClassmatePDFExporter()
    path = exporter.export_lesson(
        "SS1 First Term Week 1\n\nTopic: Introduction to Digital Technologies\n"
        + ("A readable paragraph with punctuation, spaces and measured line wrapping. " * 10),
        tmp_path / "lesson.pdf",
    )
    assert path.is_file() and path.stat().st_size > 500


def test_legacy_cli_refuses_handwriting_samples(capsys):
    from scripts.end_to_end_pipeline import main as pipeline_main

    result = pipeline_main([
        "--sample", "does-not-need-to-exist.png",
        "--class", "SS2",
        "--term", "Second Term",
        "--week", "2",
    ])
    captured = capsys.readouterr()
    assert result == 2
    assert "Handwriting-to-font export is disabled" in captured.err
