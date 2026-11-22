from types import SimpleNamespace

import numpy as np

from model.htr import HTRPipeline
from model.htr_providers import KrakenConfig, KrakenProvider, HTRProviderConfigurationError


def image():
    return np.full((24, 80), 255, dtype=np.uint8)


def provider_for(record):
    return KrakenProvider(
        KrakenConfig("/already-injected/model.mlmodel"),
        model=object(),
        recognizer=lambda _model, _image, _segmentation: [record],
    )


def test_kraken_cuts_become_explicit_boxes_and_skip_whitespace():
    record = SimpleNamespace(
        prediction="a b",
        cuts=[[(2, 3), (10, 3), (10, 19), (2, 19)], None, [(22, 4), (31, 4), (31, 20), (22, 20)]],
        confidences=[0.98, 0.91, 0.87],
    )

    result = provider_for(record).recognize_lines([image()])[0]

    assert result["text"] == "a b"
    assert result["character_boxes"] == [
        {"bbox": [2, 3, 9, 17], "confidence": 0.98},
        {"bbox": [22, 4, 10, 17], "confidence": 0.87},
    ]
    assert result["character_geometry_mismatch"] is False
    assert result["confidence"] == (0.98 + 0.87) / 2


def test_malformed_cut_is_retained_as_invalid_geometry():
    record = SimpleNamespace(
        prediction="ab",
        cuts=["not-a-polygon", [(20, 2), (30, 2), (30, 20), (20, 20)]],
        confidences=[0.95, 0.96],
    )

    result = provider_for(record).recognize_lines([image()])[0]

    assert result["character_boxes"][0] == {"bbox": None, "confidence": 0.95}
    assert result["character_boxes"][1]["bbox"] == [20, 2, 11, 19]


def test_cut_count_mismatch_is_marked_for_review_not_reindexed():
    record = SimpleNamespace(
        prediction="abc",
        cuts=[[(2, 2), (10, 2), (10, 20), (2, 20)]],
        confidences=[0.99],
    )

    raw = provider_for(record).recognize_lines([image()])[0]
    assert raw["character_geometry_mismatch"] is True
    assert len(raw["character_boxes"]) == 3

    class FakeAnalysis:
        lines = [SimpleNamespace(index=0, bbox=(0, 0, 80, 24), crop=image())]

    recognized = HTRPipeline(provider_for(record)).recognize(FakeAnalysis())
    assert recognized.lines[0].needs_review is True
    assert "character geometry count mismatch" in recognized.lines[0].review_reasons


def test_low_confidence_character_is_preserved_for_localized_alignment_review():
    record = SimpleNamespace(
        prediction="ab",
        cuts=[[(2, 2), (10, 2), (10, 20), (2, 20)], [(20, 2), (30, 2), (30, 20), (20, 20)]],
        confidences=[0.99, 0.20],
    )

    result = provider_for(record).recognize_lines([image()])[0]

    assert result["character_boxes"][1]["confidence"] == 0.20
    assert result["confidence"] == (0.99 + 0.20) / 2


def test_kraken_environment_requires_an_explicit_model(monkeypatch):
    monkeypatch.delenv("HTR_KRAKEN_MODEL", raising=False)
    from model.htr_providers import kraken_from_environment

    try:
        kraken_from_environment()
    except HTRProviderConfigurationError as exc:
        assert "HTR_KRAKEN_MODEL" in str(exc)
    else:
        raise AssertionError("Kraken must not be enabled without an explicit model path")
