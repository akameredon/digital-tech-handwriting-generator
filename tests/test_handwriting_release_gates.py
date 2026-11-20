"""Tests for open handwriting acceptance (real teacher photos)."""
from pathlib import Path
import sys
import numpy as np
import pytest

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
        {"label": char, "image": np.pad(np.ones((16, 8), dtype=np.uint8) * 255, 2), "row": 1,
         "confirmed": True, "provenance": "teacher_corrected"}
        for char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    ]
    path = FontCompiler().compile(glyphs, tmp_path / "partial.ttf")
    assert path.is_file() and path.stat().st_size > 500


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



def test_partial_font_maps_only_confirmed_characters(tmp_path):
    from fontTools.ttLib import TTFont as ReadFont
    glyphs = [
        {"label": char, "image": np.pad(np.ones((16, 8), dtype=np.uint8) * 255, 2),
         "row": 1, "confirmed": True, "provenance": "teacher_corrected"}
        for char in "ABCDEFGH"
    ]
    path = FontCompiler().compile(glyphs, tmp_path / "confirmed-only.ttf")
    with ReadFont(str(path)) as font:
        cmap = font.getBestCmap()
        assert set(map(chr, cmap)) == set("ABCDEFGH")
        assert "." not in cmap
        assert "Z" not in cmap


def test_font_compiler_ignores_unconfirmed_or_unlabeled_components(tmp_path):
    unsafe = [
        {"label": char, "image": np.pad(np.ones((16, 8), dtype=np.uint8) * 255, 2),
         "row": 1, "confirmed": False, "provenance": "recognizer"}
        for char in "ABCDEFGH"
    ]
    with pytest.raises(FontCompilationError):
        FontCompiler().compile(unsafe, tmp_path / "must-not-build.ttf")


def test_pdf_exporter_accepts_partial_font_and_uses_fallback(tmp_path):
    glyphs = [
        {"label": char, "image": np.pad(np.ones((16, 8), dtype=np.uint8) * 255, 2),
         "row": 1, "confirmed": True, "provenance": "teacher_corrected"}
        for char in "ABCDEFGH"
    ]
    font_path = FontCompiler().compile(glyphs, tmp_path / "partial.ttf")
    output = tmp_path / "mixed-font.pdf"
    exporter = ClassmatePDFExporter(font_path=str(font_path))
    pdf_path = exporter.export_lesson("ABCDEFGH — missing characters use standard fallback.", output)
    assert pdf_path.is_file() and pdf_path.stat().st_size > 500
