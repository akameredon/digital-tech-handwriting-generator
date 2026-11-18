"""
Basic tests for the NERDC curriculum engine.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from curriculum.nerdc_schemes import get_lesson, list_all_topics, NERDC_DIGITAL_TECHNOLOGIES
from curriculum.prompt_engine import build_prompt
from curriculum.validator import validate_lesson_structure, is_exam_or_break_week


def test_schemes_exist():
    assert "SS1" in NERDC_DIGITAL_TECHNOLOGIES
    assert "SS2" in NERDC_DIGITAL_TECHNOLOGIES
    assert "SS3" in NERDC_DIGITAL_TECHNOLOGIES


def test_get_lesson_valid():
    lesson = get_lesson("SS2", "Second Term", 2)
    assert lesson is not None
    assert "topic" in lesson
    assert "Python" in lesson["topic"] or "Programming" in lesson["topic"]


def test_get_lesson_invalid():
    lesson = get_lesson("SS2", "Second Term", 99)
    assert lesson is None


def test_list_all_topics():
    topics = list_all_topics("SS1")
    assert len(topics) > 20
    assert all("class" in t and "week" in t for t in topics)


def test_build_prompt():
    prompt = build_prompt("SS1", "First Term", 3)
    assert prompt is not None
    assert "Number Systems" in prompt
    assert "Behavioral Learning Objectives" in prompt


def test_is_exam_week():
    assert is_exam_or_break_week("Midterm Test") is True
    assert is_exam_or_break_week("Introduction to Python") is False


def test_validator_basic():
    sample = """
    Behavioral Learning Objectives
    Key Concepts
    Conceptual Explanation
    Practical
    Class Activity
    Quick Test
    Assignment
    1. First objective
    """
    report = validate_lesson_structure(sample)
    assert report["valid"] is True


if __name__ == "__main__":
    test_schemes_exist()
    test_get_lesson_valid()
    test_get_lesson_invalid()
    test_list_all_topics()
    test_build_prompt()
    test_is_exam_week()
    test_validator_basic()
    print("All curriculum tests passed.")
