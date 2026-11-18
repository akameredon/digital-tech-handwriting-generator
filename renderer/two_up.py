"""
2-up print helper for Classmate-style notes.
Produces a landscape PDF with two columns for cutting into exercise books.
"""

from pathlib import Path
from typing import Optional
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import black, HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import textwrap
import re


def export_2up(
    text: str,
    output_path: str | Path,
    title: str = "Digital Technologies Lesson Note",
    font_path: Optional[str] = None,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    font_name = "Helvetica"
    if font_path and Path(font_path).exists():
        try:
            pdfmetrics.registerFont(TTFont("TeacherHW", font_path))
            font_name = "TeacherHW"
        except Exception:
            pass

    page_w, page_h = landscape(A4)
    c = canvas.Canvas(str(output_path), pagesize=landscape(A4))

    lines = []
    for raw in text.splitlines():
        raw = raw.rstrip()
        if not raw:
            lines.append("")
            continue
        cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", raw)
        cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
        lines.extend(textwrap.wrap(cleaned, width=52) or [""])

    col_w = page_w / 2 - 18 * mm
    line_h = 6.2 * mm
    lines_per_col = int((page_h - 30 * mm) / line_h)
    pink = HexColor("#E91E63")
    blue = HexColor("#90CAF9")

    def draw_column(start_idx: int, x0: float) -> int:
        c.setStrokeColor(blue)
        c.setLineWidth(0.5)
        y = page_h - 18 * mm
        for _ in range(lines_per_col + 1):
            c.line(x0, y, x0 + col_w, y)
            y -= line_h
        c.setStrokeColor(pink)
        c.setLineWidth(1.1)
        c.line(x0 + 4 * mm, 12 * mm, x0 + 4 * mm, page_h - 15 * mm)

        c.setFillColor(black)
        y = page_h - 18 * mm - line_h
        idx = start_idx
        for _ in range(lines_per_col):
            if idx >= len(lines):
                break
            c.setFont(font_name, 9)
            c.drawString(x0 + 6 * mm, y, lines[idx][:65])
            y -= line_h
            idx += 1
        return idx

    idx = 0
    while idx < len(lines):
        idx = draw_column(idx, 12 * mm)
        if idx < len(lines):
            idx = draw_column(idx, page_w / 2 + 6 * mm)
        c.setFont(font_name, 8)
        c.drawCentredString(page_w / 2, 6 * mm, title[:50])
        c.showPage()

    c.save()
    return output_path
