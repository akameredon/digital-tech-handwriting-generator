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

def test_byte_upload_intake_accepts_natural_page(tmp_path):
    from io import BytesIO
    from fastapi import UploadFile
    from main import analyze_natural_handwriting_page
    path = tmp_path / "natural.png"
    make_natural_page(path)
    upload = UploadFile(file=BytesIO(path.read_bytes()), filename="teacher-page.png",
                        headers={"content-type": "image/png"})
    response = __import__("asyncio").run(analyze_natural_handwriting_page(upload))
    assert response["status"] == "analyzed"
    assert response["recognition_status"] == "not_configured"
    assert response["analysis"]["line_count"] >= 2
    assert "blur_score" in response["analysis"]


def test_byte_upload_rejects_payload_over_limit():
    from ingestion.open_handwriting import HandwritingIntakeError, MAX_NATURAL_PAGE_BYTES
    try:
        OpenHandwritingIntake().analyze_bytes(b"x" * (MAX_NATURAL_PAGE_BYTES + 1))
    except HandwritingIntakeError as exc:
        assert "12 MB" in str(exc)
    else:
        raise AssertionError("Oversized upload must be rejected before decoding")


def test_byte_upload_rejects_invalid_image():
    from ingestion.open_handwriting import HandwritingIntakeError
    try:
        OpenHandwritingIntake().analyze_bytes(b"not-an-image")
    except HandwritingIntakeError as exc:
        assert "valid" in str(exc).lower()
    else:
        raise AssertionError("Invalid image bytes must be rejected")


def test_upload_api_rejects_unsupported_mime_type():
    from io import BytesIO
    from fastapi import UploadFile, HTTPException
    from main import analyze_natural_handwriting_page
    upload = UploadFile(file=BytesIO(b"not an image"), filename="page.gif",
                        headers={"content-type": "image/gif"})
    try:
        __import__("asyncio").run(analyze_natural_handwriting_page(upload))
    except HTTPException as exc:
        assert exc.status_code == 415
    else:
        raise AssertionError("Unsupported MIME type must be rejected")
