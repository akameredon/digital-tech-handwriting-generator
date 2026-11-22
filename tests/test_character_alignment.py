import cv2
import numpy as np

from model.character_alignment import CharacterAligner, CharacterAlignmentError


def sample(label="a", verified=True, bbox=(10, 20, 30, 40)):
    image = np.full((80, 100), 255, dtype=np.uint8)
    cv2.line(image, (20, 65), (45, 15), 0, 5)
    cv2.line(image, (45, 15), (70, 65), 0, 5)
    return {
        "label": label,
        "image": image,
        "bbox": bbox,
        "source_width": 100,
        "source_height": 80,
        "label_source": "worksheet_cell_teacher_confirmation_required" if verified else "guessed_position",
    }


def test_alignment_preserves_sequence_source_position_and_quality():
    result = CharacterAligner().align([sample("a"), sample("b", bbox=(50, 20, 30, 40))])
    assert [item.label for item in result.observations] == ["a", "b"]
    assert [item.sequence_index for item in result.observations] == [0, 1]
    assert result.observations[1].source_bbox == (50, 20, 30, 40)
    assert result.observations[0].normalized_bbox == (0.1, 0.25, 0.3, 0.5)
    assert result.observations[0].image.shape == (96, 96)
    assert 0.0 <= result.observations[0].quality <= 1.0


def test_unverified_label_is_rejected_and_reported():
    result = CharacterAligner().align([sample("a", verified=False), sample("b")])
    assert [item.label for item in result.observations] == ["b"]
    assert any("not verified" in warning for warning in result.warnings)


def test_duplicate_labels_are_retained_as_variants():
    result = CharacterAligner().align([sample("a"), sample("a")])
    assert len(result.observations) == 2
    assert any("Repeated labels" in warning for warning in result.warnings)


def test_all_invalid_samples_raise():
    try:
        CharacterAligner().align([sample("ab")])
    except CharacterAlignmentError as exc:
        assert "No verifiable" in str(exc)
    else:
        raise AssertionError("Invalid labels should not produce an alignment result")


def line_image():
    image = np.full((32, 90), 255, dtype=np.uint8)
    cv2.rectangle(image, (4, 8), (20, 25), 0, -1)
    cv2.rectangle(image, (30, 6), (48, 26), 0, -1)
    return image


def test_line_text_without_character_geometry_is_not_positionally_mapped():
    result = CharacterAligner().align_recognized_line(
        line_image(), (100, 200, 90, 32), {"text": "ab", "confidence": 0.99}
    )
    assert result.candidates == []
    assert result.review[0]["reason"] == "character_geometry_missing"


def test_geometry_count_mismatch_is_rejected_instead_of_zipped():
    result = CharacterAligner().align_recognized_line(
        line_image(), (100, 200, 90, 32), {
            "text": "ab",
            "character_boxes": [{"bbox": [2, 6, 22, 22], "confidence": 0.99}],
        }
    )
    assert result.candidates == []
    assert result.review[0]["reason"] == "character_geometry_count_mismatch"


def test_explicit_geometry_creates_candidates_and_confirmation_promotes_them():
    result = CharacterAligner().align_recognized_line(
        line_image(), (100, 200, 90, 32), {
            "text": "ab",
            "character_boxes": [
                {"bbox": [2, 6, 22, 22], "confidence": 0.99},
                {"bbox": [28, 4, 23, 25], "confidence": 0.97},
            ],
        }
    )
    assert result.ready_for_confirmation is True
    assert [candidate.label for candidate in result.candidates] == ["a", "b"]
    confirmed = CharacterAligner().confirm_candidates(
        result.candidates, {0: "a", 1: "b"}, source_width=400, source_height=400
    )
    assert [item.label for item in confirmed.observations] == ["a", "b"]
    assert all("teacher_confirmed" in item.source for item in confirmed.observations)


def test_low_confidence_character_is_localized_for_review():
    result = CharacterAligner().align_recognized_line(
        line_image(), (0, 0, 90, 32), {
            "text": "ab",
            "character_boxes": [
                {"bbox": [2, 6, 22, 22], "confidence": 0.99},
                {"bbox": [28, 4, 23, 25], "confidence": 0.40},
            ],
        }
    )
    assert len(result.candidates) == 1
    assert result.review[0]["label"] == "b"
