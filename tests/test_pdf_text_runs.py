"""Regression tests for readable PDF text with standard and partial fonts."""
from io import BytesIO
from uuid import uuid4

import numpy as np
import pytest
from pypdf import PdfReader
from reportlab.lib.colors import Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from model.font_compiler import FontCompiler
from renderer.pdf_exporter import ClassmatePDFExporter


@pytest.fixture
def partial_exporter(tmp_path):
    # Deliberately exclude lowercase characters, spaces, and punctuation.
    name = f"TestPartial{uuid4().hex}"
    glyphs = [
        {"label": char, "image": np.ones((20, 12), dtype=np.uint8) * 255, "row": 1}
        for char in "ABCDEFGH"
    ]
    path = FontCompiler().compile(glyphs, tmp_path / "partial.ttf", family_name=name)
    exporter = ClassmatePDFExporter(font_path=str(path), font_name=name)
    try:
        yield exporter
    finally:
        exporter.release_temporary_font()


def _pdf_page(buffer, pdf):
    pdf.save()
    buffer.seek(0)
    return PdfReader(buffer).pages[0]


def _shown_characters(page, exporter):
    """Read ASCII Tj runs and their positions from the actual PDF content stream."""
    fonts = page["/Resources"]["/Font"].get_object()
    x = y = size = None
    current_font = None
    color = None
    chars = []
    runs = []
    for operands, operator in page.get_contents().operations:
        if operator == b"rg":
            color = tuple(float(value) for value in operands)
        elif operator == b"Tm":
            x, y = map(float, operands[-2:])
        elif operator == b"Tf":
            current_font = fonts[operands[0]].get_object()
            size = float(operands[1])
        elif operator == b"Tj":
            assert x is not None and current_font is not None
            raw = operands[0].original_bytes
            run = raw.decode("ascii")
            is_custom = current_font.get("/Subtype") == "/TrueType"
            font_name = exporter.font_name if is_custom else "Helvetica"
            assert is_custom or current_font.get("/BaseFont") == "/Helvetica"
            runs.append((run, font_name))
            for byte, char in zip(raw, run):
                chars.append((char, font_name, x, y, color))
                if is_custom:
                    # Actual embedded-PDF widths, rather than measured test inputs.
                    widths = current_font["/Widths"]
                    x += float(widths[byte - int(current_font["/FirstChar"])]) * size / 1000
                else:
                    x += pdfmetrics.stringWidth(char, "Helvetica", size)
    return runs, chars


def _assert_character_positions(chars, exporter, text, x, y, size, color):
    assert len(chars) == len(text)
    for (actual_char, actual_font, actual_x, actual_y, actual_color), char in zip(chars, text):
        expected_font = exporter._font_for(char)
        assert actual_char == char
        assert actual_font == expected_font
        assert actual_x == pytest.approx(x, abs=0.0001)
        assert actual_y == pytest.approx(y, abs=0.0001)
        assert actual_color == pytest.approx((color.red, color.green, color.blue), abs=0.0001)
        x += pdfmetrics.stringWidth(char, expected_font, size)
    return x


def test_standard_font_text_is_one_extractable_run_with_original_positions():
    exporter = ClassmatePDFExporter()
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    text, x, y, size = "Week 2: clear handwriting", 33.125, 457.25, 10.25
    color = Color(0.2, 0.4, 0.6)

    end = exporter._draw_mixed(pdf, x, y, text, size, color)
    assert pdf._fontname == "Helvetica" and pdf._fontsize == size
    assert pdf._fillColorObj == color
    page = _pdf_page(buffer, pdf)

    assert page.extract_text().strip() == text
    runs, chars = _shown_characters(page, exporter)
    assert runs == [(text, "Helvetica")]
    expected_end = _assert_character_positions(chars, exporter, text, x, y, size, color)
    assert end == pytest.approx(expected_end)
    assert end - x == pytest.approx(exporter._width(text, size))


@pytest.mark.parametrize(
    ("text", "expected_runs"),
    [
        ("ABCDex GH? mixed ABCD", [
            ("ABCD", True), ("ex ", False), ("GH", True),
            ("? mixed ", False), ("ABCD", True),
        ]),
        ("xy ABcd EF!", [
            ("xy ", False), ("AB", True), ("cd ", False),
            ("EF", True), ("!", False),
        ]),
    ],
)
def test_mixed_partial_font_runs_keep_words_fallback_and_positions(
    partial_exporter, text, expected_runs,
):
    exporter = partial_exporter
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    x, y, size = 25.5, 390.75, 12
    color = Color(0.1, 0.3, 0.5)

    end = exporter._draw_mixed(pdf, x, y, text, size, color)
    assert pdf._fontname == exporter._font_for(text[-1]) and pdf._fontsize == size
    assert pdf._fillColorObj == color
    page = _pdf_page(buffer, pdf)

    assert page.extract_text().strip() == text
    runs, chars = _shown_characters(page, exporter)
    assert runs == [
        (run, exporter.font_name if custom else "Helvetica")
        for run, custom in expected_runs
    ]
    expected_end = _assert_character_positions(chars, exporter, text, x, y, size, color)
    assert end == pytest.approx(expected_end)
    assert end - x == pytest.approx(exporter._width(text, size))
    fonts = page["/Resources"]["/Font"].get_object().values()
    assert any(
        font.get_object().get("/FontDescriptor")
        and font.get_object()["/FontDescriptor"].get_object().get("/FontFile2")
        for font in fonts
    )


def test_mixed_font_preserves_extractable_unicode_fallback(partial_exporter):
    exporter = partial_exporter
    text, x, size = "ABCD—café GH?", 20, 12
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)

    end = exporter._draw_mixed(pdf, x, 400, text, size)
    assert exporter._font_for("—") == exporter._font_for("é") == "Helvetica"
    assert end - x == pytest.approx(exporter._width(text, size))
    assert _pdf_page(buffer, pdf).extract_text().strip() == text


def test_wrapping_and_line_origins_use_mixed_character_widths(partial_exporter):
    exporter = partial_exporter
    text, size = "ABCDex GH? ABCD", 12
    max_width = exporter._width("ABCD", size) + 0.001
    lines = exporter._wrap(text, max_width, size)
    assert lines == ["ABCD", "ex", "GH?", "ABCD"]
    assert all(exporter._width(line, size) <= max_width for line in lines)

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    x, y, line_height = 42.0, 510.0, 18.0
    color = Color(0.1, 0.3, 0.5)
    for index, line in enumerate(lines):
        end = exporter._draw_mixed(pdf, x, y - index * line_height, line, size, color)
        assert end - x == pytest.approx(exporter._width(line, size))
    page = _pdf_page(buffer, pdf)

    assert page.extract_text().strip() == "\n".join(lines)
    _, chars = _shown_characters(page, exporter)
    offset = 0
    for index, line in enumerate(lines):
        _assert_character_positions(
            chars[offset:offset + len(line)], exporter, line,
            x, y - index * line_height, size, color,
        )
        offset += len(line)
    assert offset == len(chars)


def test_empty_text_keeps_cursor_and_existing_font_but_sets_color():
    exporter = ClassmatePDFExporter()
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.setFont("Courier", 17)
    color = Color(0.1, 0.3, 0.5)

    assert exporter._draw_mixed(pdf, 12.5, 200, "", 9, color) == 12.5
    assert pdf._fontname == "Courier" and pdf._fontsize == 17
    assert pdf._fillColorObj == color
    assert not _pdf_page(buffer, pdf).extract_text().strip()
