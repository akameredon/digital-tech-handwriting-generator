"""
Pedagogical Validator
Ensures generated lesson notes follow the required schema and stay grade-appropriate.
"""

from typing import Dict, List, Any
import re


REQUIRED_SECTIONS = [
    "Behavioral Learning Objectives",
    "Key Concepts",
    "Conceptual Explanation",
    "Practical",
    "Class Activity",
    "Quick Test",
    "Assignment",
]


def validate_lesson_structure(text: str) -> Dict[str, Any]:
    """
    Check that a generated lesson note contains the mandatory sections.
    Returns a report with pass/fail and missing sections.
    """
    report = {
        "valid": True,
        "missing_sections": [],
        "warnings": [],
        "word_count": len(text.split()),
    }

    lower = text.lower()
    for section in REQUIRED_SECTIONS:
        if section.lower() not in lower:
            report["missing_sections"].append(section)
            report["valid"] = False

    # Basic length sanity checks
    if report["word_count"] < 180:
        report["warnings"].append("Lesson appears too short (< 180 words)")
    if report["word_count"] > 2200:
        report["warnings"].append("Lesson appears excessively long (> 2200 words)")

    # Check for presence of objectives numbering
    if not re.search(r"1\.\s+", text):
        report["warnings"].append("Objectives may not be properly numbered")

    return report


def is_exam_or_break_week(topic: str) -> bool:
    """Helper to identify non-content weeks."""
    keywords = ["midterm", "examination", "revision", "closing", "break", "mock", "graduation"]
    return any(k in topic.lower() for k in keywords)
