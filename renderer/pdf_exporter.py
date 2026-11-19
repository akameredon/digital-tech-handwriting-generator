"""
PDF Exporter – Classmate-style ruled notebook pages.
Custom handwriting is used only for characters actually present in the
compiled font. Unsupported characters (especially spaces and punctuation)
are rendered with a readable system font instead of the font's .notdef box.
"""
from pathlib import Path
from typing import Optional, Set
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import black, HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import textwrap
import re

try:
    from fontTools.ttLib import TTFont as FontToolsTTFont
except ImportError:
    FontToolsTTFont = None


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
        self.handwriting_codepoints: Set[int] = set()

        if font_path and Path(font_path).is_file():
            try:
                if FontToolsTTFont is None:
                    raise RuntimeError("fontTools is required to inspect handwriting font coverage")
                inspected = FontToolsTTFont(font_path, lazy=True)
                self.handwriting_codepoints = set((inspected.getBestCmap() or {}).keys())
                inspected.close()
                if not self.handwriting_codepoints:
                    raise ValueError("The compiled font has no usable character map")
                pdfmetrics.registerFont(TTFont(font_name, font_path))
                self.font_name = font_name
                self.font_name_bold = font_name
                print(
                    f"Using custom handwriting font: {font_path} "
                    f"({len(self.handwriting_codepoints)} mapped characters)"
                )
            except Exception as exc:
                self.handwriting_codepoints = set()
                self.font_name = "Helvetica"
                self.font_name_bold = "Helvetica-Bold"
                print(f"Handwriting font rejected; using readable fallback: {exc}")

    def _draw_text(self, c: canvas.Canvas, x: float, y: float, text: str, size: float):
        """Draw mixed-font text without emitting missing-glyph .notdef boxes."""
        cursor = x
        for char in text:
            use_handwriting = (
                self.font_name not in ("Helvetica", "Helvetica-Bold")
                and ord(char) in self.handwriting_codepoints
            )
            font = self.font_name if use_handwriting else "Helvetica"
            c.setFont(font, size)
            c.drawString(cursor, y, char)
            cursor += pdfmetrics.stringWidth(char, font, size)

    def _draw_ruled_page(self, c: canvas.Canvas):
        c.setStrokeColor(self.pink)
        c.setLineWidth(1.2)
        c.line(
            self.margin_left - 3 * mm,
            self.margin_bottom,
            self.margin_left - 3 * mm,
            self.page_height - self.margin_top + 5 * mm,
        )
        c.setStrokeColor(self.blue_line)
        c.setLineWidth(0.6)
        y = self.page_height - self.margin_top
        while y > self.margin_bottom:
            c.line(
                self.margin_left - 5 * mm,
                y,
                self.page_width - self.margin_right,
                y,
            )
            y -= self.line_height

    def _draw_header(self, c: canvas.Canvas, title: str, page_num: int):
        c.setFillColor(black)
        self._draw_text(c, self.margin_left, self.page_height - 12 * mm, title[:60], 9)
        self._draw_text(
            c,
            self.page_width - self.margin_right - 28 * mm,
            self.page_height - 12 * mm,
            f"Page {page_num}",
            8,
        )

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
                    self._draw_text(c, self.margin_left, y, line[:95], 10)
                else:
                    self._draw_text(c, self.margin_left, y, line[:95], 10)
                y -= self.line_height
                idx += 1
            c.showPage()
            page_num += 1
        c.save()
        return output_path
