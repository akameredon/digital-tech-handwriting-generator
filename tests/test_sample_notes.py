"""Prepared lesson indexing must be complete, deterministic, and curriculum-safe."""
import asyncio
from pathlib import Path

from curriculum.sample_notes import get_prepared_lesson, prepared_lesson_index
from main import build_lesson_payload, get_lesson_note


ROOT = Path(__file__).resolve().parents[1]


def test_all_curriculum_matched_notes_are_discovered():
    index = prepared_lesson_index(ROOT / "samples")
    assert len(list((ROOT / "samples").rglob("*.md"))) == 26
    assert len(index) == 26
    for class_level, term, week in index:
        payload = build_lesson_payload(class_level, term, week)
        assert payload["content_status"] == "prepared"
        assert payload["lesson_note"] == get_prepared_lesson(class_level, term, week, ROOT / "samples")


def test_corrected_hardware_note_is_available_only_for_week_four():
    hardware = get_prepared_lesson("SS1", "First Term", 4, ROOT / "samples")
    assert hardware is not None
    assert "Storage Devices and Input/Output Devices" in hardware
    midterm = build_lesson_payload("SS1", "First Term", 5)
    assert midterm["content_status"] == "outline"
    assert midterm["topic"] == "Midterm Test"


def test_api_marks_each_indexed_note_as_prepared():
    for class_level, term, week in prepared_lesson_index(ROOT / "samples"):
        payload = asyncio.run(get_lesson_note(class_level, term, week))
        assert payload["content_status"] == "prepared"
