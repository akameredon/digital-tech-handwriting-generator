import json

import numpy as np
from PIL import Image

from model.htr_benchmark import (
    benchmark_provider,
    character_error_rate,
    load_cases,
    word_error_rate,
)
from model.htr_providers import TrOCRConfig, TrOCRProvider


class FakeProvider:
    name = "fake-benchmark"
    model_id = "fixture"

    def recognize_lines(self, lines):
        return [{"text": "Hello world", "confidence": 0.96} for _ in lines]


def test_error_rates_are_normalized_and_bounded():
    assert character_error_rate("Hello world", "hello world") == 0.0
    assert word_error_rate("hello world", "hello there") == 0.5
    assert character_error_rate("", "anything") == 1.0


def test_manifest_and_benchmark_report(tmp_path):
    image_path = tmp_path / "line.png"
    Image.fromarray(np.zeros((20, 80), dtype=np.uint8)).save(image_path)
    manifest = tmp_path / "cases.jsonl"
    manifest.write_text(json.dumps({
        "case_id": "greeting",
        "image_path": str(image_path),
        "reference": "Hello world",
    }) + "\n", encoding="utf-8")

    report = benchmark_provider(FakeProvider(), load_cases(manifest))

    assert report.case_count == 1
    assert report.character_error_rate == 0.0
    assert report.word_error_rate == 0.0
    assert report.cases[0].passed is True
    assert report.mean_latency_ms >= 0
    assert report.p95_latency_ms >= 0


def test_trocr_provider_is_lazy_and_does_not_download_on_construction():
    provider = TrOCRProvider(TrOCRConfig(local_files_only=True))
    assert provider.model_id == "microsoft/trocr-small-handwritten"
    assert provider._model is None
    assert provider._processor is None
