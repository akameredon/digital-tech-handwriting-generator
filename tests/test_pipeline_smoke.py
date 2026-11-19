"""Smoke tests for the complete handwriting → font → PDF pipeline."""
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ingestion.preprocessor import DEFAULT_SAMPLE_ROWS
from model.font_compiler import FontCompiler
from renderer.pdf_exporter import ClassmatePDFExporter


def make_synthetic_glyph() -> np.ndarray:
    image = np.zeros((80, 60), dtype=np.uint8)
    image[10:70, 15:45] = 255
    image[20:30, 20:40] = 0
    return image


def test_font_compiler_smoke():
    glyphs = [
        {"label": char, "image": make_synthetic_glyph(), "row": row_no}
        for row_no, row in enumerate(DEFAULT_SAMPLE_ROWS, 1)
        for char in row
    ]
    out = Path("test_synthetic_font.ttf")
    result = FontCompiler().compile(glyphs, out, family_name="TestHandwriting")
    assert result is not None and out.exists() and out.stat().st_size > 500
    out.unlink(missing_ok=True)


def test_pdf_exporter_smoke():
    out = Path("test_smoke_lesson.pdf")
    result = ClassmatePDFExporter().export_lesson(
        "**Class:** SS2\n**Topic:** Test\n\nThis is a smoke test note.",
        out, title="Smoke Test"
    )
    assert result.exists() and result.stat().st_size > 500
    result.unlink(missing_ok=True)


if __name__ == "__main__":
    test_font_compiler_smoke()
    test_pdf_exporter_smoke()
    print("All pipeline smoke tests passed.")
