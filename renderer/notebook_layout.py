"""Notebook layout planning and paginated ruled-page PDF rendering."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import textwrap
from typing import List, Optional, Tuple

from reportlab.lib.colors import HexColor, black
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


@dataclass(frozen=True)
class LayoutLine:
    text: str
    heading: bool = False
    source_block: int = 0


@dataclass(frozen=True)
class NotebookPage:
    number: int
    lines: Tuple[LayoutLine, ...]


@dataclass
class NotebookLayout:
    pages: List[NotebookPage]
    page_width: float
    page_height: float
    line_height: float
    margin_left: float
    margin_right: float
    lines_per_page: int

    @property
    def page_count(self) -> int:
        return len(self.pages)


class NotebookLayoutEngine:
    """Turn lesson Markdown into stable, line-aware notebook pages."""

    def __init__(self, page_width: float = A4[0], page_height: float = A4[1], line_height: float = 7.2 * mm,
                 margin_left: float = 20 * mm, margin_right: float = 15 * mm, margin_top: float = 18 * mm,
                 margin_bottom: float = 15 * mm, chars_per_line: int = 78):
        self.page_width, self.page_height = page_width, page_height
        self.line_height = line_height
        self.margin_left, self.margin_right = margin_left, margin_right
        self.margin_top, self.margin_bottom = margin_top, margin_bottom
        self.chars_per_line = chars_per_line
        self.lines_per_page = max(1, int((page_height - margin_top - margin_bottom) / line_height) - 1)

    @staticmethod
    def _clean(text: str) -> str:
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"`([^`]+)`", r"\1", text)
        return re.sub(r"\s+", " ", text).strip()

    def _lines(self, markdown: str) -> List[LayoutLine]:
        output: List[LayoutLine] = []
        block = 0
        for raw in markdown.splitlines():
            cleaned = self._clean(raw)
            if not cleaned:
                output.append(LayoutLine("", False, block)); block += 1; continue
            heading = bool(re.match(r"^(#{1,6}\s+|Class:|Term:|Week:|Topic:|Behavioral Learning Objectives$|Key Concepts / Definitions$|Step-by-Step Conceptual Explanation$|Practical / Worked Example$|Class Activity / Guided Practice$|End-of-Lesson Quick Test$|Assignment$)", cleaned, re.I))
            wrapped = textwrap.wrap(cleaned, width=self.chars_per_line, break_long_words=True, break_on_hyphens=False) or [""]
            output.extend(LayoutLine(line, heading and index == 0, block) for index, line in enumerate(wrapped))
            block += 1
        return output

    def plan(self, markdown: str) -> NotebookLayout:
        lines = self._lines(markdown)
        pages = [NotebookPage(number, tuple(lines[start:start + self.lines_per_page])) for number, start in enumerate(range(0, len(lines), self.lines_per_page), 1)]
        if not pages:
            pages = [NotebookPage(1, tuple())]
        return NotebookLayout(pages, self.page_width, self.page_height, self.line_height, self.margin_left, self.margin_right, self.lines_per_page)


class NotebookPDFRenderer:
    """Render a planned layout with ruled pages and predictable pagination."""

    def __init__(self, layout_engine: Optional[NotebookLayoutEngine] = None):
        self.engine = layout_engine or NotebookLayoutEngine()

    def render(self, markdown: str, output_path: str | Path, title: str = "Digital Technologies Lesson Note") -> NotebookLayout:
        layout = self.engine.plan(markdown)
        output = Path(output_path); output.parent.mkdir(parents=True, exist_ok=True)
        pdf = canvas.Canvas(str(output), pagesize=(layout.page_width, layout.page_height))
        for page in layout.pages:
            self._page(pdf, layout, page, title)
            pdf.showPage()
        pdf.save()
        return layout

    @staticmethod
    def _page(pdf: canvas.Canvas, layout: NotebookLayout, page: NotebookPage, title: str) -> None:
        width, height = layout.page_width, layout.page_height
        pink, blue = HexColor("#E91E63"), HexColor("#90CAF9")
        x_left, x_right = layout.margin_left, width - layout.margin_right
        y = height - 18 * mm
        pdf.setStrokeColor(blue); pdf.setLineWidth(.6)
        while y > 15 * mm:
            pdf.line(x_left - 5 * mm, y, x_right, y); y -= layout.line_height
        pdf.setStrokeColor(pink); pdf.setLineWidth(1.2)
        pdf.line(x_left - 3 * mm, 15 * mm, x_left - 3 * mm, height - 13 * mm)
        pdf.setFillColor(black)
        y = height - 18 * mm - layout.line_height
        for line in page.lines:
            if line.heading:
                pdf.setFont("Helvetica-Bold", 9.5)
            else:
                pdf.setFont("Helvetica", 9)
            pdf.drawString(x_left, y, line.text[:110])
            if line.heading:
                pdf.setStrokeColor(HexColor("#1A237E")); pdf.line(x_left, y - 1.5, min(x_right, x_left + pdf.stringWidth(line.text[:110], "Helvetica-Bold", 9.5)), y - 1.5); pdf.setStrokeColor(blue)
            y -= layout.line_height
        pdf.setFont("Helvetica", 7); pdf.setFillColor(HexColor("#526174"))
        pdf.drawRightString(x_right, 8 * mm, f"{title[:55]}  ·  Page {page.number}/{layout.page_count}")
