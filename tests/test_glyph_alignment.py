"""Tests for evidence-backed character-to-glyph alignment."""
import numpy as np
import pytest

from ingestion.glyph_alignment import (
    CharacterObservation,
    GlyphAlignmentError,
    align_character_boxes,
    confirm_observation,
    confirmed_glyphs,
    coverage_report,
)


def test_character_boxes_are_bound_to_recognized_text_not_guessed():
    line = np.full((24, 60), 255, dtype=np.uint8)
    line[4:20, 2:12] = 0
    line[4:20, 20:30] = 0
    result = align_character_boxes(line, "A B", [(2, 4, 10, 16), (20, 4, 10, 16)], [0.7, 0.99])
    assert [item.char for item in result] == ["A", "B"]
    assert [item.confirmed for item in result] == [False, False]
    assert result[0].image.shape == (16, 10)


def test_box_count_mismatch_is_rejected_not_evenly_split():
    line = np.full((20, 60), 255, dtype=np.uint8)
    with pytest.raises(GlyphAlignmentError, match="Cannot align"):
        align_character_boxes(line, "ABC", [(0, 0, 10, 20), (10, 0, 10, 20)])


def test_out_of_bounds_box_is_rejected():
    line = np.full((20, 20), 255, dtype=np.uint8)
    with pytest.raises(GlyphAlignmentError, match="outside"):
        align_character_boxes(line, "A", [(18, 0, 5, 10)])


def test_teacher_correction_confirms_only_the_selected_character():
    line = np.full((20, 20), 255, dtype=np.uint8)
    item = align_character_boxes(line, "O", [(2, 2, 10, 14)], [0.42])[0]
    corrected = confirm_observation(item, "0")
    assert not item.confirmed
    assert corrected.char == "0"
    assert corrected.confirmed
    assert corrected.provenance == "teacher_corrected"
    assert [glyph["label"] for glyph in confirmed_glyphs([item, corrected])] == ["0"]


def test_coverage_report_discloses_missing_and_uncertain_characters():
    line = np.full((20, 40), 255, dtype=np.uint8)
    observations = align_character_boxes(line, "AB", [(0, 0, 10, 10), (10, 0, 10, 10)])
    confirmed = confirm_observation(observations[0])
    report = coverage_report([confirmed, observations[1]], "ABC")
    assert report["confirmed_characters"] == ["A"]
    assert report["uncertain_characters"] == ["B"]
    assert report["missing_characters"] == ["B", "C"]
