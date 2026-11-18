"""
Smoke test for the handwriting → font → PDF pipeline using synthetic glyphs.
"""

import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from model.font_compiler import FontCompiler
from renderer.pdf_exporter import ClassmatePDFExporter


def make_synthetic_glyph() -> np.ndarray:
    img = np.zeros((80, 60), dtype=np.uint8)
    img[10:70, 15:45] = 255
    img[20:30, 20:40] = 0
    return img


def test_font_compiler_smoke():
    glyphs = [
        {"label": "A", "image": make_synthetic_glyph()},
        {"label": "B", "image": make_synthetic_glyph()},
        {"label": "1", "image": make_synthetic_glyph()},
    ]
    compiler = FontCompiler()
    out = Path("test_synthetic_font.ttf")
    result = compiler.compile(glyphs, out, family_name="TestHandwriting")
    assert result is not None
    assert out.exists()
    assert out.stat().st_size > 500
    out.unlink(missing_ok=True)
    print("Font compiler smoke test passed")


def test_pdf_exporter_smoke():
    exporter = ClassmatePDFExporter()
    out = Path("test_smoke_lesson.pdf")
    result = exporter.export_lesson(
        "**Class:** SS2\n**Topic:** Test\n\nThis is a smoke test note.",
        out,
        title="Smoke Test"
    )
    assert result.exists()
    assert result.stat().st_size > 1000
    result.unlink(missing_ok=True)
    print("PDF exporter smoke test passed")


if __name__ == "__main__":
    test_font_compiler_smoke()
    test_pdf_exporter_smoke()
    print("All pipeline smoke tests passed.")
