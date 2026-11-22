"""Notebook-style PDF exporter matching Classmate teaching-note layout.

Draws:
- Ruled classmate page (pink margin + blue lines)
- Underlined section headings
- Body text in teacher handwriting font (with Helvetica fallback)
- Rounded boxes for code / worked examples
- Simple flow arrows for A → B → C sequences
- Key-idea callout bars
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import black, HexColor, Color, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from fontTools.ttLib import TTFont as FontToolsTTFont

PINK = HexColor("#E91E63")
BLUE_LINE = HexColor("#90CAF9")
BOX_STROKE = HexColor("#5C6BC0")
BOX_FILL = HexColor("#EEF2FF")
KEY_FILL = HexColor("#E8EAF6")
KEY_STROKE = HexColor("#3949AB")
HEADING_COLOR = HexColor("#1A237E")
ARROW_COLOR = HexColor("#3949AB")


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
        self.page_width, self.page_height = page_width, page_height
        self.margin_left, self.margin_right = margin_left, margin_right
        self.margin_top, self.margin_bottom = margin_top, margin_bottom
        self.line_height = line_height
        self.font_name = "Helvetica"
        self.fallback_font = "Helvetica"
        self.custom_supported = set()
        if font_path and Path(font_path).is_file():
            with FontToolsTTFont(str(font_path), checkChecksums=2) as parsed:
                cmap = parsed.getBestCmap() or {}
            self.custom_supported = {chr(codepoint) for codepoint in cmap}
            pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
            self.font_name = font_name

    def _font_for(self, char: str) -> str:
        if self.font_name != "Helvetica" and char in self.custom_supported:
            return self.font_name
        return self.fallback_font

    def release_temporary_font(self) -> None:
        """Release a uniquely named request font after its PDF has been written."""
        if self.font_name == "Helvetica":
            return
        from reportlab.lib import fonts as family_fonts

        name = self.font_name
        font = pdfmetrics._fonts.pop(name, None)
        face = getattr(font, "face", None)
        face_name = getattr(face, "name", None)
        if face_name:
            pdfmetrics._dynFaceNames.pop(face_name, None)
        for bold in (0, 1):
            for italic in (0, 1):
                key = (name.lower(), bold, italic)
                ps_name = family_fonts._tt2ps_map.pop(key, None)
                if ps_name:
                    family_fonts._ps2tt_map.pop(ps_name.lower(), None)
        self.font_name = "Helvetica"
        self.custom_supported = set()

    def _width(self, text: str, size: float) -> float:
        return sum(
            pdfmetrics.stringWidth(char, self._font_for(char), size) for char in text
        )

    def _draw_mixed(self, c: canvas.Canvas, x: float, y: float, text: str, size: float,
                    color: Color = black) -> float:
        c.setFillColor(color)
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

    def _draw_ruled_page(self, c: canvas.Canvas):
        c.setStrokeColor(PINK)
        c.setLineWidth(1.2)
        c.line(
            self.margin_left - 3 * mm,
            self.margin_bottom,
            self.margin_left - 3 * mm,
            self.page_height - self.margin_top + 5 * mm,
        )
        c.setStrokeColor(BLUE_LINE)
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

    def _draw_underline(self, c: canvas.Canvas, x: float, y: float, text: str, size: float):
        w = self._width(text, size)
        c.setStrokeColor(HEADING_COLOR)
        c.setLineWidth(1.0)
        c.line(x, y - 1.5, x + w, y - 1.5)

    def _draw_rounded_box(
        self,
        c: canvas.Canvas,
        x: float,
        y_top: float,
        width: float,
        height: float,
        fill: Color = BOX_FILL,
        stroke: Color = BOX_STROKE,
        radius: float = 4,
    ):
        c.setFillColor(fill)
        c.setStrokeColor(stroke)
        c.setLineWidth(1.0)
        c.roundRect(x, y_top - height, width, height, radius, stroke=1, fill=1)

    def _draw_flow_row(
        self,
        c: canvas.Canvas,
        items: List[str],
        x: float,
        y: float,
        max_width: float,
        size: float = 9.0,
    ) -> float:
        if not items:
            return y
        gap = 6
        arrow_w = 14
        pads = 8
        widths = [self._width(t, size) + pads * 2 for t in items]
        total = sum(widths) + arrow_w * (len(items) - 1) + gap * (len(items) - 1)
        if total > max_width:
            for i, text in enumerate(items):
                bw = min(self._width(text, size) + pads * 2, max_width)
                bh = self.line_height * 1.3
                self._draw_rounded_box(c, x, y + 2, bw, bh, fill=white, stroke=BOX_STROKE)
                self._draw_mixed(c, x + pads, y - bh + 10, text, size, ARROW_COLOR)
                y -= bh + 4
                if i < len(items) - 1:
                    c.setStrokeColor(ARROW_COLOR)
                    c.setFillColor(ARROW_COLOR)
                    mid = x + bw / 2
                    c.line(mid, y + 2, mid, y - 6)
                    path = c.beginPath()
                    path.moveTo(mid - 3, y - 2)
                    path.lineTo(mid + 3, y - 2)
                    path.lineTo(mid, y - 7)
                    path.close()
                    c.drawPath(path, fill=1, stroke=0)
                    y -= 10
            return y

        cursor = x
        bh = self.line_height * 1.35
        for i, text in enumerate(items):
            bw = widths[i]
            self._draw_rounded_box(c, cursor, y + 2, bw, bh, fill=white, stroke=BOX_STROKE)
            self._draw_mixed(c, cursor + pads, y - bh + 11, text, size, ARROW_COLOR)
            cursor += bw
            if i < len(items) - 1:
                ax0 = cursor + 2
                ax1 = cursor + arrow_w - 2
                mid_y = y - bh / 2 + 2
                c.setStrokeColor(ARROW_COLOR)
                c.setFillColor(ARROW_COLOR)
                c.setLineWidth(1.2)
                c.line(ax0, mid_y, ax1 - 3, mid_y)
                path = c.beginPath()
                path.moveTo(ax1 - 4, mid_y + 3)
                path.lineTo(ax1, mid_y)
                path.lineTo(ax1 - 4, mid_y - 3)
                path.close()
                c.drawPath(path, fill=1, stroke=0)
                cursor += arrow_w + gap
        return y - bh - 4

    def _draw_key_idea(
        self,
        c: canvas.Canvas,
        text: str,
        x: float,
        y: float,
        max_width: float,
        size: float = 9.0,
    ) -> float:
        lines = self._wrap(text, max_width - 12, size)
        height = len(lines) * self.line_height + 8
        self._draw_rounded_box(
            c, x, y + 4, max_width, height, fill=KEY_FILL, stroke=KEY_STROKE, radius=5
        )
        ty = y - 2
        for line in lines:
            self._draw_mixed(c, x + 6, ty, line, size, KEY_STROKE)
            ty -= self.line_height
        return ty - 4

    @staticmethod
    def _clean_md(line: str) -> str:
        s = line.rstrip()
        s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
        s = re.sub(r"`([^`]+)`", r"\1", s)
        s = re.sub(r"^#+\s*", "", s)
        return s

    def _is_heading(self, cleaned: str) -> bool:
        s = cleaned.strip()
        if not s or len(s) > 55:
            return False
        if re.match(r"^(Class|Term|Week|Topic)\s*:", s, re.I):
            return False
        exact = {
            "behavioral learning objectives",
            "key concepts / definitions",
            "key concepts",
            "definitions",
            "step-by-step conceptual explanation",
            "practical / worked example",
            "worked example",
            "class activity / guided practice",
            "class activity",
            "guided practice",
            "end-of-lesson quick test",
            "quick test",
            "assignment",
        }
        low = s.lower().rstrip(":")
        if low in exact:
            return True
        if s.endswith(":") and len(s) <= 40:
            return True
        words = s.split()
        if (
            2 <= len(words) <= 8
            and not s.endswith(".")
            and sum(1 for w in words if w[:1].isupper()) >= max(2, len(words) - 1)
        ):
            starters = ("by the", "students", "write a", "use ", "the ", "a ", "an ")
            if any(low.startswith(p) for p in starters):
                return False
            return True
        return False

    def _is_key_idea_line(self, cleaned: str) -> bool:
        low = cleaned.lower().strip()
        return low.startswith("key idea") or low.startswith("bottom takeaway") or low.startswith("remember:")

    def _parse_flow(self, cleaned: str) -> Optional[List[str]]:
        if "→" not in cleaned and "->" not in cleaned:
            return None
        parts = re.split(r"\s*(?:→|->)\s*", cleaned)
        parts = [p.strip(" :") for p in parts if p.strip()]
        if len(parts) >= 2 and all(len(p) < 40 for p in parts):
            return parts
        return None

    def export_lesson(
        self,
        text: str,
        output_path: str | Path,
        title: str = "Digital Technologies Lesson Note",
    ) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(output_path), pagesize=(self.page_width, self.page_height))
        c.setTitle(title)

        max_width = self.page_width - self.margin_left - self.margin_right
        content_top = self.page_height - self.margin_top - self.line_height
        content_bottom = self.margin_bottom + self.line_height
        y = content_top
        page_num = 1
        self._draw_ruled_page(c)

        def new_page():
            nonlocal y, page_num
            c.showPage()
            page_num += 1
            self._draw_ruled_page(c)
            y = content_top
            draw_header()

        def draw_header():
            c.setFillColor(black)
            self._draw_mixed(
                c, self.margin_left, self.page_height - 12 * mm, title[:55], 8
            )
            c.setFont("Helvetica", 8)
            c.setFillColor(HexColor("#546E7A"))
            c.drawRightString(
                self.page_width - self.margin_right,
                self.page_height - 12 * mm,
                f"Page {page_num}",
            )

        def need_space(lines_needed: float = 1):
            nonlocal y
            if y - lines_needed * self.line_height < content_bottom:
                new_page()

        draw_header()

        in_code = False
        code_lines: List[str] = []

        def flush_code():
            nonlocal y, code_lines
            if not code_lines:
                return
            size = 8.5
            pad = 6
            wrapped_all: List[str] = []
            for raw in code_lines:
                wrapped_all.extend(self._wrap(raw if raw else " ", max_width - 16, size))
            height = len(wrapped_all) * self.line_height + pad * 2
            need_space(height / self.line_height + 1)
            self._draw_rounded_box(
                c,
                self.margin_left,
                y + 4,
                max_width,
                height,
                fill=BOX_FILL,
                stroke=BOX_STROKE,
            )
            ty = y - 2
            for line in wrapped_all:
                self._draw_mixed(c, self.margin_left + 8, ty, line, size, HEADING_COLOR)
                ty -= self.line_height
            y = ty - 6
            code_lines = []

        for raw in text.splitlines():
            stripped = raw.strip()

            if stripped.startswith("```"):
                if in_code:
                    in_code = False
                    flush_code()
                else:
                    in_code = True
                    code_lines = []
                continue
            if in_code:
                code_lines.append(raw.rstrip("\n"))
                continue

            if stripped in ("---", "***", "___"):
                need_space(0.8)
                y -= self.line_height * 0.5
                continue

            cleaned = self._clean_md(raw)
            if not cleaned.strip():
                y -= self.line_height * 0.35
                continue

            if self._is_key_idea_line(cleaned):
                need_space(3)
                y = self._draw_key_idea(
                    c, cleaned, self.margin_left, y, max_width, size=9.0
                )
                continue

            flow = self._parse_flow(cleaned)
            if flow:
                need_space(3)
                y = self._draw_flow_row(
                    c, flow, self.margin_left, y, max_width, size=9.0
                )
                y -= 4
                continue

            is_heading = self._is_heading(cleaned)
            size = 11.0 if is_heading else 9.5
            color = HEADING_COLOR if is_heading else black
            wrapped = self._wrap(cleaned, max_width, size)

            for i, line in enumerate(wrapped):
                need_space(1.2)
                self._draw_mixed(c, self.margin_left, y, line, size, color)
                if is_heading and i == len(wrapped) - 1:
                    self._draw_underline(c, self.margin_left, y, line, size)
                y -= self.line_height

            if is_heading:
                y -= 2

        flush_code()
        c.save()
        if not output_path.is_file() or output_path.stat().st_size < 500:
            raise RuntimeError("PDF export did not produce a valid non-empty document.")
        return output_path
