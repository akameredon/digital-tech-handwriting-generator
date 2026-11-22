"""Real-world acceptance gates for the handwriting lesson pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
from pypdf import PdfReader

from curriculum.validator import validate_lesson_structure


@dataclass(frozen=True)
class RecognitionScore:
    character_accuracy: float
    word_accuracy: float
    character_error_rate: float
    passed: bool


@dataclass(frozen=True)
class SimilarityScore:
    structural_similarity: float
    ink_density_delta: float
    passed: bool


@dataclass(frozen=True)
class AcceptanceReport:
    recognition: Optional[RecognitionScore]
    handwriting: Optional[SimilarityScore]
    lesson_valid: bool
    lesson_word_count: int
    pdf_pages: int
    pdf_has_text: bool
    pdf_printable: bool
    checks: Dict[str, bool]
    warnings: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(self.checks.values())

    def public_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "recognition": self.recognition.__dict__ if self.recognition else None,
            "handwriting": self.handwriting.__dict__ if self.handwriting else None,
            "lesson_valid": self.lesson_valid,
            "lesson_word_count": self.lesson_word_count,
            "pdf_pages": self.pdf_pages,
            "pdf_has_text": self.pdf_has_text,
            "pdf_printable": self.pdf_printable,
            "checks": self.checks,
            "warnings": self.warnings,
        }


def _edit_distance(left: str, right: str) -> int:
    row = list(range(len(right) + 1))
    for i, char in enumerate(left, 1):
        previous, row[0] = row[0], i
        for j, other in enumerate(right, 1):
            old = row[j]
            row[j] = min(row[j] + 1, row[j - 1] + 1, previous + (char != other))
            previous = old
    return row[-1]


def score_recognition(expected: str, actual: str) -> RecognitionScore:
    expected_norm = re.sub(r"\s+", " ", expected.strip().casefold())
    actual_norm = re.sub(r"\s+", " ", actual.strip().casefold())
    distance = _edit_distance(expected_norm, actual_norm)
    char_accuracy = max(0.0, 1.0 - distance / max(1, len(expected_norm)))
    expected_words, actual_words = expected_norm.split(), actual_norm.split()
    word_distance = _edit_distance(" ".join(expected_words), " ".join(actual_words))
    word_accuracy = max(0.0, 1.0 - word_distance / max(1, len(" ".join(expected_words))))
    cer = distance / max(1, len(expected_norm))
    return RecognitionScore(char_accuracy, word_accuracy, cer, char_accuracy >= .90 and word_accuracy >= .80)


def score_handwriting_similarity(reference: np.ndarray, generated: np.ndarray, threshold: float = .72) -> SimilarityScore:
    def normalize(image: np.ndarray) -> np.ndarray:
        array = np.asarray(image)
        if array.ndim == 3:
            array = cv2.cvtColor(array, cv2.COLOR_BGR2GRAY)
        return cv2.resize(array, (256, 256), interpolation=cv2.INTER_AREA)
    left, right = normalize(reference), normalize(generated)
    left_edges = cv2.Canny(left, 50, 150).astype(np.float32) / 255.0
    right_edges = cv2.Canny(right, 50, 150).astype(np.float32) / 255.0
    structural = float(SequenceMatcher(None, left_edges.ravel().tolist(), right_edges.ravel().tolist()).ratio())
    left_density = float(np.mean(left < 180)); right_density = float(np.mean(right < 180))
    delta = abs(left_density - right_density)
    passed = structural >= threshold and delta <= .12
    return SimilarityScore(structural, delta, passed)


def score_pdf(path: str | Path) -> tuple[int, bool, bool, List[str]]:
    warnings: List[str] = []
    reader = PdfReader(str(path))
    pages = len(reader.pages)
    extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
    has_text = bool(extracted.strip())
    printable = pages > 0 and all(float(page.mediabox.width) > 0 and float(page.mediabox.height) > 0 for page in reader.pages)
    if not has_text: warnings.append("PDF has no extractable text.")
    if not printable: warnings.append("PDF contains an invalid page box.")
    return pages, has_text, printable, warnings


class AcceptanceEvaluator:
    """Combine independent gates; no single attractive image can hide a failure."""

    def evaluate(self, *, expected_text: Optional[str] = None, recognized_text: Optional[str] = None,
                 reference_image: Optional[np.ndarray] = None, generated_image: Optional[np.ndarray] = None,
                 lesson_text: Optional[str] = None, pdf_path: Optional[str | Path] = None) -> AcceptanceReport:
        recognition = score_recognition(expected_text, recognized_text) if expected_text is not None and recognized_text is not None else None
        handwriting = score_handwriting_similarity(reference_image, generated_image) if reference_image is not None and generated_image is not None else None
        lesson_report = validate_lesson_structure(lesson_text) if lesson_text is not None else {"valid": False, "word_count": 0}
        pages = has_text = printable = 0 if pdf_path is None else None
        warnings: List[str] = []
        if pdf_path is not None:
            pages, has_text, printable, pdf_warnings = score_pdf(pdf_path); warnings.extend(pdf_warnings)
        checks = {
            "recognition": recognition is not None and recognition.passed,
            "handwriting": handwriting is not None and handwriting.passed,
            "lesson": bool(lesson_report["valid"]),
            "pdf": pdf_path is not None and bool(pages and has_text and printable),
        }
        return AcceptanceReport(recognition, handwriting, bool(lesson_report["valid"]), lesson_report["word_count"], int(pages or 0), bool(has_text), bool(printable), checks, warnings)
