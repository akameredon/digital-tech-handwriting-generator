import numpy as np
import pytest

from ingestion.open_handwriting import PageAnalysis, RecognitionUnavailable, TextLineRegion
from model.htr import HTRPipeline


class FakeHTR:
    name = "fake-htr"

    def recognize_lines(self, lines):
        assert len(lines) == 2
        return [
            {"text": "Good morning", "confidence": 0.96},
            {"text": "cIass", "confidence": 0.61, "alternatives": ["class", "glass"], "ambiguous_characters": ["I/l"]},
        ]


def analysis():
    crop = np.zeros((30, 120), dtype=np.uint8)
    return PageAnalysis(120, 80, "usable", [], [
        TextLineRegion(0, (5, 10, 110, 20), crop, 0.2),
        TextLineRegion(1, (5, 40, 110, 20), crop, 0.2),
    ])


def test_htr_normalizes_provider_results_and_flags_ambiguity():
    result = HTRPipeline(FakeHTR()).recognize(analysis())
    assert result.text == "Good morning\ncIass"
    assert result.provider == "fake-htr"
    assert result.lines[0].needs_review is False
    assert result.lines[1].needs_review is True
    assert "class" in result.lines[1].alternatives
    assert "competing alternatives returned" in result.lines[1].review_reasons
    assert result.needs_review is True


def test_percentage_confidence_is_supported_and_text_is_cleaned():
    class Provider:
        name = "percentage"
        def recognize_lines(self, lines):
            return [{"text": "  hello\tworld\n", "confidence": 92} for _ in lines]
    result = HTRPipeline(Provider()).recognize(analysis())
    assert result.lines[0].text == "hello world"
    assert result.lines[0].confidence == 0.92


def test_missing_provider_is_explicit():
    with pytest.raises(RecognitionUnavailable, match="not configured"):
        HTRPipeline().recognize(analysis())
