"""Regression tests for strict segmentation, glyph mapping and rendering safety."""
from pathlib import Path
import sys
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ingestion.preprocessor import (
    HandwritingPreprocessor, HandwritingSampleError,
    DEFAULT_SAMPLE_ROWS, DEFAULT_SAMPLE_ORDER,
)
from model.font_compiler import FontCompiler, FontCompilationError
from renderer.pdf_exporter import ClassmatePDFExporter


def synthetic_template():
    image = np.zeros((560, 1100), dtype=np.uint8)
    y_positions = [30, 110, 190, 270, 350, 430]
    for row_index, (row, y) in enumerate(zip(DEFAULT_SAMPLE_ROWS, y_positions)):
        for column, _ in enumerate(row):
            x = 20 + column * 24
            image[y:y+22, x:x+12] = 255
    return image


def test_template_maps_only_when_every_row_count_matches():
    processor = HandwritingPreprocessor()
    glyphs = processor.extract_glyphs(synthetic_template(), DEFAULT_SAMPLE_ORDER)
    assert "".join(g["label"] for g in glyphs) == "".join(DEFAULT_SAMPLE_ROWS)
    assert len(glyphs) == len(DEFAULT_SAMPLE_ORDER)


def test_template_rejects_missing_character_instead_of_shifting_labels():
    image = synthetic_template()
    # Erase one complete component from row 1.
    image[30:52, 20:32] = 0
    with pytest.raises(HandwritingSampleError, match="Row 1 requires"):
        HandwritingPreprocessor().extract_glyphs(image, DEFAULT_SAMPLE_ORDER)


def test_template_rejects_wrong_expected_order():
    with pytest.raises(HandwritingSampleError, match="approved sample-sheet"):
        HandwritingPreprocessor().extract_glyphs(synthetic_template(), list(reversed(DEFAULT_SAMPLE_ORDER)))


def test_font_compiler_rejects_incomplete_glyph_set(tmp_path):
    with pytest.raises(FontCompilationError, match="Missing"):
        FontCompiler().compile([{"label": "A", "image": np.ones((20, 12), dtype=np.uint8) * 255}],
                               tmp_path / "incomplete.ttf")


def test_font_compiler_builds_and_verifies_complete_cmap(tmp_path):
    glyphs = [
        {"label": char, "image": np.ones((20, 12), dtype=np.uint8) * 255,
         "row": row_no}
        for row_no, row in enumerate(DEFAULT_SAMPLE_ROWS, 1)
        for char in row
    ]
    path = FontCompiler().compile(glyphs, tmp_path / "complete.ttf")
    assert path.is_file() and path.stat().st_size > 500


def test_pdf_wrap_uses_measured_width_and_keeps_long_tokens():
    exporter = ClassmatePDFExporter()
    text = "A" * 300 + " punctuation, spaces and a final sentence."
    lines = exporter._wrap(text, 100, 10)
    assert len(lines) > 1
    assert "".join(lines).replace(" ", "") == text.replace(" ", "")
    assert all(exporter._width(line, 10) <= 100.01 for line in lines)


def test_pdf_export_creates_nonempty_document(tmp_path):
    exporter = ClassmatePDFExporter()
    path = exporter.export_lesson(
        "SS1 First Term Week 1\n\nTopic: Introduction to Digital Technologies\n"
        + ("A readable paragraph with punctuation, spaces and measured line wrapping. " * 15),
        tmp_path / "lesson.pdf",
    )
    assert path.is_file() and path.stat().st_size > 500
