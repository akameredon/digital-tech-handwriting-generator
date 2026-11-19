"""Notebook-style PDF exporter with measured wrapping and per-character fallback."""
from pathlib import Path
from typing import Iterable, List, Optional, Tuple
import re

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import black, HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from fontTools.ttLib import TTFont as FontToolsTTFont

REQUIRED_TEXT_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")


class ClassmatePDFExporter:
    def __init__(self, page_width=A4[0], page_height=A4[1],
                 margin_left=20*mm, margin_right=15*mm,
                 margin_top=18*mm, margin_bottom=15*mm,
                 line_height=7.2*mm, font_path: Optional[str] = None,
                 font_name: str = "TeacherHandwriting"):
        self.page_width, self.page_height = page_width, page_height
        self.margin_left, self.margin_right = margin_left, margin_right
        self.margin_top, self.margin_bottom = margin_top, margin_bottom
        self.line_height = line_height
        self.pink, self.blue_line = HexColor("#E91E63"), HexColor("#90CAF9")
        self.font_name = "Helvetica"
        self.fallback_font = "Helvetica"
        self.custom_supported = set()
        if font_path and Path(font_path).is_file():
            with FontToolsTTFont(str(font_path), checkChecksums=2) as parsed:
                cmap = parsed.getBestCmap() or {}
                self.custom_supported = {chr(codepoint) for codepoint in cmap}
            missing_core = REQUIRED_TEXT_CHARS - self.custom_supported
            if missing_core:
                raise ValueError(
                    "Handwriting font is missing required letters or digits: "
                    + "".join(sorted(missing_core))
                )
            pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
            self.font_name = font_name

    def _draw_ruled_page(self, c: canvas.Canvas):
        c.setStrokeColor(self.pink)
        c.setLineWidth(1.2)
        c.line(self.margin_left-3*mm, self.margin_bottom,
               self.margin_left-3*mm, self.page_height-self.margin_top+5*mm)
        c.setStrokeColor(self.blue_line)
        c.setLineWidth(0.6)
        y = self.page_height-self.margin_top
        while y > self.margin_bottom:
            c.line(self.margin_left-5*mm, y, self.page_width-self.margin_right, y)
            y -= self.line_height

    def _font_for(self, char: str) -> str:
        if self.font_name != "Helvetica" and char in self.custom_supported:
            return self.font_name
        return self.fallback_font

    def _width(self, text: str, size: float) -> float:
        return sum(pdfmetrics.stringWidth(char, self._font_for(char), size) for char in text)

    def _draw_mixed(self, c: canvas.Canvas, x: float, y: float, text: str, size: float):
        cursor = x
        for char in text:
            font = self._font_for(char)
            c.setFont(font, size)
            c.drawString(cursor, y, char)
            cursor += pdfmetrics.stringWidth(char, font, size)
        return cursor

    def _wrap(self, text: str, max_width: float, size: float) -> List[str]:
        if not text:
            return [""]
        words = text.split()
        if not words:
            return [""]
        lines: List[str] = []
        current = ""
        for word in words:
            candidate = word if not current else current + " " + word
            if self._width(candidate, size) <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
                current = ""
            # Split an exceptionally long token without clipping or losing text.
            piece = ""
            for char in word:
                if piece and self._width(piece + char, size) > max_width:
                    lines.append(piece)
                    piece = char
                else:
                    piece += char
            current = piece
        if current:
            lines.append(current)
        return lines

    def export_lesson(self, text: str, output_path: str | Path,
                      title: str = "Digital Technologies Lesson Note") -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(output_path), pagesize=(self.page_width, self.page_height))
        c.setTitle(title)
        max_width = self.page_width-self.margin_left-self.margin_right
        content_top = self.page_height-self.margin_top-self.line_height
        content_bottom = self.margin_bottom+self.line_height
        y = content_top
        page_num = 1
        self._draw_ruled_page(c)

        def new_page():
            nonlocal y, page_num
            c.showPage()
            page_num += 1
            self._draw_ruled_page(c)
            y = content_top

        def draw_header():
            c.setFillColor(black)
            self._draw_mixed(c, self.margin_left, self.page_height-12*mm, title[:60], 8)
            c.setFont("Helvetica", 8)
            c.drawRightString(self.page_width-self.margin_right,
                              self.page_height-12*mm, f"Page {page_num}")

        draw_header()
        for raw in text.splitlines():
            cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", raw.rstrip())
            cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
            is_heading = bool(cleaned.strip()) and (
                cleaned.isupper() or cleaned.endswith(":")
                or any(word in cleaned for word in ("Objectives", "Assignment", "Key Concepts"))
            )
            size = 10.0 if is_heading else 9.5
            wrapped = self._wrap(cleaned, max_width, size) if cleaned else [""]
            for line in wrapped:
                if y < content_bottom:
                    new_page()
                    draw_header()
                c.setFillColor(black)
                self._draw_mixed(c, self.margin_left, y, line, size)
                y -= self.line_height
        c.save()
        if not output_path.is_file() or output_path.stat().st_size < 500:
            raise RuntimeError("PDF export did not produce a valid non-empty document.")
        return output_path
