import cv2
import numpy as np

from ingestion.open_handwriting import PageAnalysis, TextLineRegion
from model.glyph_alignment_pipeline import align_document_glyphs, confirm_document_glyphs, learn_writer_profile
from model.htr import HTRDocumentResult, HTRLineResult


def line_image():
    image = np.full((32, 90), 255, dtype=np.uint8)
    cv2.rectangle(image, (4, 8), (20, 25), 0, -1)
    cv2.rectangle(image, (30, 6), (48, 26), 0, -1)
    return image


def analysis():
    crop = line_image()
    return PageAnalysis(90, 32, "usable", [], [
        TextLineRegion(0, (10, 20, 90, 32), crop, 0.2),
    ])


def htr(character_boxes=()):
    return HTRDocumentResult([
        HTRLineResult(
            line_index=0,
            bbox=(10, 20, 90, 32),
            text="ab",
            confidence=0.96,
            alternatives=(),
            needs_review=False,
            review_reasons=(),
            provider="geometry-provider",
            character_boxes=tuple(character_boxes),
        ),
    ], "geometry-provider", [])


def test_document_bridge_requires_explicit_geometry():
    result = align_document_glyphs(analysis(), htr())
    assert result.candidates == []
    assert result.needs_review is True
    assert result.lines[0].review[0]["reason"] == "character_geometry_missing"


def test_document_bridge_returns_candidates_with_explicit_geometry():
    result = align_document_glyphs(analysis(), htr([
        {"bbox": [2, 6, 22, 22], "confidence": 0.99},
        {"bbox": [28, 4, 23, 25], "confidence": 0.97},
    ]))
    assert [candidate.label for candidate in result.candidates] == ["a", "b"]
    assert result.needs_review is False
    assert result.candidates[0].source_bbox == (12, 26, 22, 22)


def test_confirmed_candidates_are_the_only_profile_observations():
    pending = align_document_glyphs(analysis(), htr([
        {"bbox": [2, 6, 22, 22], "confidence": 0.99},
        {"bbox": [28, 4, 23, 25], "confidence": 0.97},
    ]))

    confirmed = confirm_document_glyphs(
        pending,
        {"0:0": "a"},
        source_width=90,
        source_height=32,
    )
    assert [observation.label for observation in confirmed.observations] == ["a"]

    learned = learn_writer_profile(confirmed, writer_name="Teacher")
    assert learned.profile.name == "Teacher"
    assert learned.coverage == {"a": 1}
