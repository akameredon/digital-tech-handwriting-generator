from pathlib import Path
import sys

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ingestion.calibration_sheet import (
    CELL_HEIGHT,
    CELL_WIDTH,
    DEFAULT_SAMPLE_ROWS,
    GRID_BOTTOM,
    GRID_COLUMNS,
    GRID_LEFT,
    GRID_RIGHT,
    GRID_ROWS,
    GRID_TOP,
    PAGE_HEIGHT,
    PAGE_WIDTH,
    CalibrationSheetError,
    extract_calibration_glyphs,
    write_calibration_sheet,
)


def _make_calibration_image(width: int = 1600, filled: bool = True) -> np.ndarray:
    height = round(width * PAGE_HEIGHT / PAGE_WIDTH)
    image = np.full((height, width, 3), 255, dtype=np.uint8)

    def px(x: float) -> int:
        return round(x / PAGE_WIDTH * width)

    def py(y: float) -> int:
        return round((PAGE_HEIGHT - y) / PAGE_HEIGHT * height)

    # Match the generated light gray worksheet grid.
    for column in range(GRID_COLUMNS + 1):
        x = px(GRID_LEFT + column * CELL_WIDTH)
        cv2.line(image, (x, py(GRID_BOTTOM)), (x, py(GRID_TOP)), (185, 190, 200), 2)
    for row in range(GRID_ROWS + 1):
        y = py(GRID_TOP - row * CELL_HEIGHT)
        cv2.line(image, (px(GRID_LEFT), y), (px(GRID_RIGHT), y), (185, 190, 200), 2)

    # Distinct dot counts identify all four corners and prevent 180-degree relabeling.
    marker_centers = [
        (8 * 72 / 25.4, PAGE_HEIGHT - 8 * 72 / 25.4),
        (PAGE_WIDTH - 8 * 72 / 25.4, PAGE_HEIGHT - 8 * 72 / 25.4),
        (PAGE_WIDTH - 8 * 72 / 25.4, 8 * 72 / 25.4),
        (8 * 72 / 25.4, 8 * 72 / 25.4),
    ]
    spacing = 2.6 * 72 / 25.4
    dot_groups = [
        [(0, 0)],
        [(-spacing / 2, 0), (spacing / 2, 0)],
        [(-spacing, 0), (0, 0), (spacing, 0)],
        [(-spacing / 2, -spacing / 2), (spacing / 2, -spacing / 2),
         (-spacing / 2, spacing / 2), (spacing / 2, spacing / 2)],
    ]
    radius = max(2, round(0.8 * 72 / 25.4 / PAGE_WIDTH * width))
    for (cx, cy), offsets in zip(marker_centers, dot_groups):
        for dx, dy in offsets:
            cv2.circle(image, (px(cx + dx), py(cy + dy)), radius, (15, 20, 30), -1)

    if filled:
        for row_index, row_chars in enumerate(DEFAULT_SAMPLE_ROWS):
            row_top = GRID_TOP - row_index * CELL_HEIGHT
            row_bottom = row_top - CELL_HEIGHT
            start = (GRID_COLUMNS - len(row_chars)) // 2
            for offset, character in enumerate(row_chars):
                column = start + offset
                cell_left = GRID_LEFT + column * CELL_WIDTH
                cell_right = cell_left + CELL_WIDTH
                x0 = round((cell_left + CELL_WIDTH * 0.23) / PAGE_WIDTH * width)
                x1 = round((cell_right - CELL_WIDTH * 0.18) / PAGE_WIDTH * width)
                y0 = round((PAGE_HEIGHT - row_top + CELL_HEIGHT * 0.30) / PAGE_HEIGHT * height)
                y1 = round((PAGE_HEIGHT - row_bottom - CELL_HEIGHT * 0.16) / PAGE_HEIGHT * height)
                baseline = min(y1 - 2, y0 + max(10, int((y1 - y0) * 0.78)))
                scale = max(0.45, min(0.8, (y1 - y0) / 58))
                cv2.putText(image, character, (x0, baseline), cv2.FONT_HERSHEY_SIMPLEX,
                            scale, (30, 35, 45), 2, cv2.LINE_AA)
    return image


def test_generated_sheet_is_a_nonempty_landscape_pdf(tmp_path):
    path = write_calibration_sheet(tmp_path / "calibration.pdf")
    assert path.is_file()
    assert path.read_bytes().startswith(b"%PDF")
    assert path.stat().st_size > 1000


def test_valid_generated_sheet_maps_cells_to_expected_characters():
    image = _make_calibration_image()
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    glyphs, missing = extract_calibration_glyphs(encoded.tobytes())
    assert not missing
    assert "".join(glyph["label"] for glyph in glyphs) == "".join(DEFAULT_SAMPLE_ROWS)
    assert all(glyph["label_source"] == "worksheet_cell_teacher_confirmation_required" for glyph in glyphs)
    assert all(np.count_nonzero(glyph["image"]) >= 5 for glyph in glyphs)


def test_blank_or_unrelated_page_is_not_positional_glyph_input():
    image = _make_calibration_image(filled=False)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    with pytest.raises(CalibrationSheetError, match="Too few handwritten characters"):
        extract_calibration_glyphs(encoded.tobytes())


def test_natural_notebook_page_is_rejected_by_calibration_path():
    page = np.full((900, 700, 3), 245, dtype=np.uint8)
    for y in (130, 250, 390, 520, 690):
        cv2.line(page, (20, y), (680, y), (190, 205, 215), 1)
    cv2.putText(page, "Good morning class", (45, 110), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX,
                1.1, (30, 40, 90), 2)
    ok, encoded = cv2.imencode(".jpg", page)
    assert ok
    with pytest.raises(CalibrationSheetError):
        extract_calibration_glyphs(encoded.tobytes())


def test_upside_down_sheet_is_rejected_instead_of_mislabeled():
    image = cv2.rotate(_make_calibration_image(), cv2.ROTATE_180)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    with pytest.raises(CalibrationSheetError, match="rotated"):
        extract_calibration_glyphs(encoded.tobytes())
