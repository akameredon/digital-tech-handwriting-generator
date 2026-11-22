from curriculum.lesson_generator import CompleteLessonGenerator, generate_complete_lesson
from curriculum.nerdc_schemes import get_lesson


def test_generates_complete_curriculum_bounded_lesson():
    draft = CompleteLessonGenerator().generate("SS2", "Second Term", 2)
    assert draft is not None
    official = get_lesson("SS2", "Second Term", 2)
    assert official["topic"] in draft.markdown
    assert draft.validation["valid"] is True
    assert draft.validation["word_count"] >= 180
    for section in ("Behavioral Learning Objectives", "Key Concepts", "Conceptual Explanation", "Practical", "Class Activity", "Quick Test", "Assignment"):
        assert section.lower() in draft.markdown.lower()


def test_convenience_api_returns_complete_markdown():
    text = generate_complete_lesson("SS1", "First Term", 3)
    assert text and "Number Systems" in text
    assert text.count("\n1.") >= 2  # objectives and quick test are both numbered


def test_unknown_week_is_not_fabricated():
    assert CompleteLessonGenerator().generate("SS2", "Second Term", 99) is None
    assert generate_complete_lesson("SS2", "Second Term", 99) is None
