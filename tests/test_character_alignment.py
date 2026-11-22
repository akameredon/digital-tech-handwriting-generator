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
