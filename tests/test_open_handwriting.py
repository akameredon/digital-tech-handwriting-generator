"""Tests for natural-layout handwriting intake; no fixed template assumptions."""
import sys
from pathlib import Path
import cv2
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ingestion.open_handwriting import OpenHandwritingIntake, RecognitionUnavailable, ConfiguredRecognizer

def make_natural_page(path: Path):
    image = np.full((900, 700, 3), 245, dtype=np.uint8)
    # Simulate ruled notebook paper and irregular handwritten-like strokes.
    for y in (130, 250, 390, 520, 690):
        cv2.line(image, (20, y), (680, y), (190, 205, 215), 1)
    cv2.putText(image, "Good morning class", (45, 110), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 1.1, (30, 40, 90), 2)
    cv2.putText(image, "Today we will learn", (55, 230), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 1.0, (30, 40, 90), 2)
    cv2.putText(image, "about digital systems", (35, 370), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 1.0, (30, 40, 90), 2)
    cv2.putText(image, "and how they work.", (70, 500), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 1.0, (30, 40, 90), 2)
    cv2.imwrite(str(path), image)

def test_accepts_natural_page_with_variable_line_count(tmp_path):
    path = tmp_path / "natural.jpg"
    make_natural_page(path)
    analysis = OpenHandwritingIntake().analyze(path)
    assert analysis.width == 700
    assert analysis.height == 900
    assert analysis.lines
    assert analysis.public_dict()["line_count"] >= 2

def test_does_not_require_six_rows_or_character_order(tmp_path):
    path = tmp_path / "natural.jpg"
    make_natural_page(path)
    result = OpenHandwritingIntake().analyze(path)
    assert len(result.lines) != 6 or result.quality in ("usable", "limited")

def test_recognition_unavailable_is_explicit_not_guessed(tmp_path):
    path = tmp_path / "natural.jpg"
    make_natural_page(path)
    analysis = OpenHandwritingIntake().analyze(path)
    recognizer = ConfiguredRecognizer()
    assert not recognizer.available
    try:
        recognizer.recognize(analysis)
    except RecognitionUnavailable as exc:
        assert "not configured" in str(exc)
    else:
        raise AssertionError("Must not fabricate recognized character labels")

def test_rejects_blank_image_with_actionable_error(tmp_path):
    path = tmp_path / "blank.jpg"
    cv2.imwrite(str(path), np.full((500, 500, 3), 255, dtype=np.uint8))
    try:
        OpenHandwritingIntake().analyze(path)
    except ValueError as exc:
        assert "handwriting" in str(exc).lower()
    else:
        raise AssertionError("Blank image should be rejected")