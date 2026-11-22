import cv2
import numpy as np
import pytest

from ingestion.segmentation import NotebookSegmenter


def notebook():
    image = np.full((900, 700, 3), 245, dtype=np.uint8)
    for y in (130, 250, 390, 520, 690):
        cv2.line(image, (20, y), (680, y), (190, 205, 215), 1)
    cv2.putText(image, "Good morning class", (45, 110), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 1.1, (30, 40, 90), 2)
    cv2.putText(image, "Today we will learn", (55, 230), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 1.0, (30, 40, 90), 2)
    cv2.putText(image, "about digital systems", (35, 370), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 1.0, (30, 40, 90), 2)
    cv2.putText(image, "and how they work.", (70, 500), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 1.0, (30, 40, 90), 2)
    return image


def test_segments_lines_paragraphs_and_regions_without_fixed_row_assumptions():
    result = NotebookSegmenter().segment(notebook())
    assert result.width == 700 and result.height == 900
    assert len(result.lines) >= 3
    assert result.paragraphs
    assert result.regions
    assert all(region.line_index < len(result.lines) for region in result.regions)
    assert result.public_dict()["line_count"] == len(result.lines)


def test_blank_page_is_rejected():
    with pytest.raises(ValueError, match="Not enough handwriting"):
        NotebookSegmenter().segment(np.full((500, 500, 3), 255, dtype=np.uint8))
