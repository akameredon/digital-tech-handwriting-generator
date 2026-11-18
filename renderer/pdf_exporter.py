"""
PDF Exporter – Classmate-style ruled notebook pages
Supports optional custom TrueType handwriting font.
"""

from pathlib import Path
from typing import Optional
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import black, HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import textwrap
import re


class ClassmatePDFExporter:
    def __init__(
        self,
        page_width=A4[0],
        page_height=A4[1],
        margin_left=20 * mm,
        margin_right=15 * mm,
        margin_top=18 * mm,
        margin_bottom=15 * mm,
        line_height=7.2 * mm,
        font_path: Optional[str] = None,
        font_name: str = "TeacherHandwriting",
    ):
        self.page_width = page_width
        self.page_height = page_height
        self.margin_left = margin_left
        self.margin_right = margin_right
        self.margin_top = margin_top
        self.margin_bottom = margin_bottom
        self.line_height = line_height
        self.pink = HexColor("#E91E63")
        self.blue_line = HexColor("#90CAF9")
        self.font_name = "Helvetica"
        self.font_name_bold = "Helvetica-Bold"

        if font_path and Path(font_path).exists():
            try:
                pdfmetrics.registerFont(TTFont(font_name, font_path))
                self.font_name = font_name
                self.font_name_bold = font_name
                print(f"Using custom handwriting font: {font_path}")
            except Exception as e:
                print(f"Could not register custom font ({e}), falling back to Helvetica")

    def _draw_ruled_page(self, c: canvas.Canvas):
        c.setStrokeColor(self.pink)
        c.setLineWidth(1.2)
        c.line(self.margin_left - 3 * mm, self.margin_bottom,
               self.margin_left - 3 * mm, self.page_height - self.margin_top + 5 * mm)
        c.setStrokeColor(self.blue_line)
        c.setLineWidth(0.6)
        y = self.page_height - self.margin_top
        while y > self.margin_bottom:
            c.line(self.margin_left - 5 * mm, y, self.page_width - self.margin_right, y)
            y -= self.line_height

    def _draw_header(self, c: canvas.Canvas, title: str, page_num: int):
        c.setFillColor(black)
        c.setFont(self.font_name_bold, 9)
        c.drawString(self.margin_left, self.page_height - 12 * mm, title[:60])
        c.setFont(self.font_name, 8)
        c.drawRightString(self.page_width - self.margin_right,
                          self.page_height - 12 * mm, f"Page {page_num}")

    def export_lesson(self, text: str, output_path: str | Path, title: str = "Digital Technologies Lesson Note") -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(output_path), pagesize=A4)
        page_num = 1

        lines = []
        for raw in text.splitlines():
            raw = raw.rstrip()
            if not raw:
                lines.append("")
                continue
            cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", raw)
            cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
            wrapped = textwrap.wrap(cleaned, width=85) or [""]
            lines.extend(wrapped)

        usable_height = self.page_height - self.margin_top - self.margin_bottom
        lines_per_page = int(usable_height / self.line_height) - 2

        idx = 0
        while idx < len(lines):
            self._draw_ruled_page(c)
            self._draw_header(c, title, page_num)
            y = self.page_height - self.margin_top - self.line_height
            for _ in range(lines_per_page):
                if idx >= len(lines):
                    break
                line = lines[idx]
                c.setFillColor(black)
                if line.isupper() or line.endswith(":") or "Objective" in line or "Assignment" in line:
                    c.setFont(self.font_name_bold, 10)
                else:
                    c.setFont(self.font_name, 10)
                c.drawString(self.margin_left, y, line[:95])
                y -= self.line_height
                idx += 1
            c.showPage()
            page_num += 1
        c.save()
        return output_path
