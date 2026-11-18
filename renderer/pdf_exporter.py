"""
PDF Exporter – Classmate-style ruled notebook pages
Produces clean, print-ready A4 PDFs that look like handwritten lesson notes
on standard Nigerian exercise book pages.
"""

from pathlib import Path
from typing import Optional
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import black, HexColor
import textwrap
import re


class ClassmatePDFExporter:
    """
    Renders lesson note text onto virtual Classmate ruled pages.
    """

    def __init__(
        self,
        page_width=A4[0],
        page_height=A4[1],
        margin_left=20 * mm,
        margin_right=15 * mm,
        margin_top=18 * mm,
        margin_bottom=15 * mm,
        line_height=7.2 * mm,
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

    def _draw_ruled_page(self, c: canvas.Canvas):
        # Pink vertical margin line
        c.setStrokeColor(self.pink)
        c.setLineWidth(1.2)
        c.line(self.margin_left - 3 * mm, self.margin_bottom,
               self.margin_left - 3 * mm, self.page_height - self.margin_top + 5 * mm)

        # Horizontal blue ruled lines
        c.setStrokeColor(self.blue_line)
        c.setLineWidth(0.6)
        y = self.page_height - self.margin_top
        while y > self.margin_bottom:
            c.line(self.margin_left - 5 * mm, y,
                   self.page_width - self.margin_right, y)
            y -= self.line_height

    def _draw_header(self, c: canvas.Canvas, title: str, page_num: int):
        c.setFillColor(black)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(self.margin_left, self.page_height - 12 * mm, title[:60])
        c.setFont("Helvetica", 8)
        c.drawRightString(self.page_width - self.margin_right,
                          self.page_height - 12 * mm, f"Page {page_num}")

    def export_lesson(
        self,
        text: str,
        output_path: str | Path,
        title: str = "Digital Technologies Lesson Note"
    ) -> Path:
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
                if line.isupper() or line.endswith(":") or line.startswith("**"):
                    c.setFont("Helvetica-Bold", 10)
                else:
                    c.setFont("Helvetica", 10)
                c.drawString(self.margin_left, y, line[:95])
                y -= self.line_height
                idx += 1

            c.showPage()
            page_num += 1

        c.save()
        return output_path


if __name__ == "__main__":
    sample = """**Class:** SS2
**Term:** Second Term
**Week:** 2
**Topic:** Introduction to Python

Behavioral Learning Objectives
By the end of this lesson, students should be able to:
1. Define Python
2. Write a simple program
"""
    exporter = ClassmatePDFExporter()
    path = exporter.export_lesson(sample, "test_classmate.pdf", "SS2 Digital Technologies")
    print(f"Sample PDF written to {path}")
