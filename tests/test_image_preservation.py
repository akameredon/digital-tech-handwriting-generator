import cv2
import numpy as np
import pytest

from ingestion.image_preservation import HandwritingPreserver


def page():
    image = np.full((500, 700, 3), 235, dtype=np.uint8)
    for y in (110, 190, 270, 350):
        cv2.putText(image, "Natural handwriting", (55, y), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 1.1, (35, 45, 80), 2)
    # Uneven lighting field to exercise normalization.
    gradient = np.tile(np.linspace(0, 35, image.shape[1], dtype=np.uint8), (image.shape[0], 1))
    image[:, :, 0] = np.clip(image[:, :, 0].astype(np.int16) - gradient, 0, 255).astype(np.uint8)
    return image


def test_preserves_detail_and_normalizes_with_explicit_page_corners():
    source = page()
    result, report = HandwritingPreserver().process(source, corners=[(30, 20), (670, 5), (690, 480), (15, 490)])
    assert result.ndim == 3 and result.shape[2] == 3
    assert report.perspective_corrected is True
    assert report.illumination_normalized is True
    assert report.output_size[0] >= 64 and report.output_size[1] >= 64
    assert report.detail_score_after > 0


def test_clean_crop_falls_back_to_full_coordinates_with_warning():
    result, report = HandwritingPreserver().process(page())
    assert result.shape[:2] == (500, 700)
    assert report.perspective_corrected is False
    assert any("quadrilateral" in warning for warning in report.warnings)


def test_invalid_image_is_rejected():
    with pytest.raises(ValueError, match="empty"):
        HandwritingPreserver().process(np.array([]))
