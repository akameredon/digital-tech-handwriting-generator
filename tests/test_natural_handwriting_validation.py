import json

import cv2
import numpy as np

from ingestion.open_handwriting import PageAnalysis, TextLineRegion
from model.natural_handwriting_validation import NaturalPageCase, load_cases, validate_pages


class FakeProvider:
    name = "fixture-provider"

    def recognize_lines(self, lines):
        return [{
            "text": "ab",
            "confidence": 0.99,
            "character_boxes": [
                {"bbox": [2, 2, 15, 20], "confidence": 0.99},
                {"bbox": [20, 2, 15, 20], "confidence": 0.98},
            ],
        } for _ in lines]


def page_analysis(path):
    image = np.full((28, 50), 255, dtype=np.uint8)
    cv2.rectangle(image, (2, 2), (16, 22), 0, -1)
    cv2.rectangle(image, (20, 2), (35, 22), 0, -1)
    return PageAnalysis(50, 28, "usable", [], [TextLineRegion(0, (0, 0, 50, 28), image, 0.3)])


def test_manifest_resolves_relative_paths_and_tracks_real_data(tmp_path):
    manifest = tmp_path / "cases.jsonl"
    manifest.write_text(json.dumps({
        "image_path": "page.png",
        "reference_text": "ab",
        "case_id": "fixture",
        "real_data": False,
    }) + "\n", encoding="utf-8")

    cases = load_cases(manifest)
    assert cases[0].image_path == str(tmp_path / "page.png")
    assert cases[0].real_data is False


def test_validation_runs_full_recognition_alignment_and_requires_real_data(tmp_path):
    case = NaturalPageCase(str(tmp_path / "fixture.png"), "ab", "fixture", real_data=False)
    report = validate_pages(
        FakeProvider(),
        [case],
        intake_factory=lambda: type("FixtureIntake", (), {"analyze": staticmethod(page_analysis)})(),
    )

    assert report.provider == "fixture-provider"
    assert report.mean_character_error_rate == 0.0
    assert report.mean_word_error_rate == 0.0
    assert report.geometry_candidate_rate == 1.0
    assert report.real_data is False
    assert report.passed is True
    assert report.cases[0].candidate_count == 2
