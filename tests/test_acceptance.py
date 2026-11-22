import cv2
import numpy as np

from curriculum.lesson_generator import generate_complete_lesson
from qa.acceptance import AcceptanceEvaluator, score_recognition, score_handwriting_similarity
from renderer.notebook_layout import NotebookPDFRenderer


def image():
    canvas = np.full((220, 500), 250, dtype=np.uint8)
    cv2.putText(canvas, "Teacher handwriting", (20, 120), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 1.1, 40, 2)
    return canvas


def test_recognition_score_is_strict_and_measurable():
    good = score_recognition("The quick brown fox", "The quick brown fox")
    bad = score_recognition("The quick brown fox", "The fox")
    assert good.passed and good.character_error_rate == 0
    assert not bad.passed and bad.character_error_rate > 0


def test_handwriting_similarity_detects_matching_and_mismatching_structure():
    source = image()
    matching = score_handwriting_similarity(source, source.copy())
    blank = score_handwriting_similarity(source, np.full_like(source, 250))
    assert matching.passed
    assert not blank.passed


def test_acceptance_evaluator_combines_lesson_pdf_and_content_gates(tmp_path):
    lesson = generate_complete_lesson("SS2", "Second Term", 2)
    pdf_path = tmp_path / "lesson.pdf"
    NotebookPDFRenderer().render(lesson, pdf_path)
    report = AcceptanceEvaluator().evaluate(
        expected_text="The quick brown fox", recognized_text="The quick brown fox",
        reference_image=image(), generated_image=image(), lesson_text=lesson, pdf_path=pdf_path,
    )
    assert report.passed
    assert all(report.checks.values())
    assert report.pdf_pages >= 1 and report.pdf_has_text and report.pdf_printable


def test_missing_evidence_fails_instead_of_passing_by_default():
    report = AcceptanceEvaluator().evaluate(lesson_text="too short")
    assert not report.passed
    assert report.checks["recognition"] is False
    assert report.checks["pdf"] is False
