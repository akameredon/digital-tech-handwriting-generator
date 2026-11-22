"""Benchmark utilities for comparing local HTR providers.

The benchmark deliberately accepts line-level image fixtures and reference
transcriptions. Page segmentation and character alignment are measured by
separate test suites; mixing them here would hide which component failed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import resource
import time
from typing import Any, Dict, Iterable, Sequence

import numpy as np
from PIL import Image

from model.htr import HTRProvider


@dataclass(frozen=True)
class HTRBenchmarkCase:
    image_path: str
    reference: str
    case_id: str = ""


@dataclass(frozen=True)
class HTRCaseResult:
    case_id: str
    image_path: str
    reference: str
    hypothesis: str
    confidence: float
    latency_ms: float
    peak_rss_mb: float
    passed: bool


@dataclass(frozen=True)
class HTRBenchmarkReport:
    provider: str
    model_id: str
    case_count: int
    character_error_rate: float
    word_error_rate: float
    mean_latency_ms: float
    p95_latency_ms: float
    peak_rss_mb: float
    review_rate: float
    cases: tuple[HTRCaseResult, ...]

    def public_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["cases"] = [asdict(case) for case in self.cases]
        return data


def _normalize(value: str) -> str:
    return " ".join(str(value).strip().split()).casefold()


def _edit_distance(left: Sequence[str], right: Sequence[str]) -> int:
    previous = list(range(len(right) + 1))
    for i, left_item in enumerate(left, 1):
        current = [i]
        for j, right_item in enumerate(right, 1):
            current.append(min(
                current[-1] + 1,
                previous[j] + 1,
                previous[j - 1] + (left_item != right_item),
            ))
        previous = current
    return previous[-1]


def character_error_rate(reference: str, hypothesis: str) -> float:
    reference_chars = list(_normalize(reference).replace(" ", ""))
    hypothesis_chars = list(_normalize(hypothesis).replace(" ", ""))
    if not reference_chars:
        return 0.0 if not hypothesis_chars else 1.0
    return _edit_distance(reference_chars, hypothesis_chars) / len(reference_chars)


def word_error_rate(reference: str, hypothesis: str) -> float:
    reference_words = _normalize(reference).split()
    hypothesis_words = _normalize(hypothesis).split()
    if not reference_words:
        return 0.0 if not hypothesis_words else 1.0
    return _edit_distance(reference_words, hypothesis_words) / len(reference_words)


def _rss_mb() -> float:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Linux reports KiB; macOS reports bytes.  Supporting both keeps the
    # report meaningful when the benchmark is run by a developer locally.
    return value / (1024.0 if value < 10_000_000 else 1024.0 * 1024.0)


def load_cases(path: str | Path) -> list[HTRBenchmarkCase]:
    """Load JSONL cases with explicit image paths and ground-truth text."""
    cases: list[HTRBenchmarkCase] = []
    for line_number, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
            image_path = str(item["image_path"])
            reference = str(item["reference"])
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ValueError(f"Invalid benchmark case on line {line_number}.") from exc
        cases.append(HTRBenchmarkCase(image_path, reference, str(item.get("case_id", line_number))))
    if not cases:
        raise ValueError("The benchmark manifest contains no cases.")
    return cases


def benchmark_provider(provider: HTRProvider, cases: Iterable[HTRBenchmarkCase]) -> HTRBenchmarkReport:
    """Run one provider and calculate accuracy/resource measurements."""
    case_results: list[HTRCaseResult] = []
    latencies: list[float] = []
    total_reference_chars = 0
    total_char_errors = 0
    total_reference_words = 0
    total_word_errors = 0
    review_count = 0

    for case in cases:
        image = np.asarray(Image.open(case.image_path).convert("RGB"))
        before = _rss_mb()
        started = time.perf_counter()
        raw_results = list(provider.recognize_lines([image]))
        latency_ms = (time.perf_counter() - started) * 1000.0
        if len(raw_results) != 1 or not isinstance(raw_results[0], dict):
            raise RuntimeError(f"Provider returned an invalid result for case {case.case_id!r}.")
        result = raw_results[0]
        hypothesis = str(result.get("text", ""))
        confidence = float(result.get("confidence", 0.0))
        review_count += confidence < 0.85
        normalized_reference = _normalize(case.reference)
        normalized_hypothesis = _normalize(hypothesis)
        char_distance = _edit_distance(
            list(normalized_reference.replace(" ", "")),
            list(normalized_hypothesis.replace(" ", "")),
        )
        word_distance = _edit_distance(normalized_reference.split(), normalized_hypothesis.split())
        reference_chars = len(normalized_reference.replace(" ", ""))
        reference_words = len(normalized_reference.split())
        total_reference_chars += reference_chars
        total_char_errors += char_distance
        total_reference_words += reference_words
        total_word_errors += word_distance
        latencies.append(latency_ms)
        case_results.append(HTRCaseResult(
            case_id=case.case_id,
            image_path=case.image_path,
            reference=case.reference,
            hypothesis=hypothesis,
            confidence=confidence,
            latency_ms=round(latency_ms, 3),
            peak_rss_mb=round(max(0.0, _rss_mb() - before), 3),
            passed=normalized_reference == normalized_hypothesis,
        ))

    ordered_latencies = sorted(latencies)
    p95_index = min(len(ordered_latencies) - 1, max(0, int(len(ordered_latencies) * 0.95) - 1))
    return HTRBenchmarkReport(
        provider=str(getattr(provider, "name", provider.__class__.__name__)),
        model_id=str(getattr(provider, "model_id", "unknown")),
        case_count=len(case_results),
        character_error_rate=total_char_errors / max(1, total_reference_chars),
        word_error_rate=total_word_errors / max(1, total_reference_words),
        mean_latency_ms=sum(latencies) / len(latencies),
        p95_latency_ms=ordered_latencies[p95_index],
        peak_rss_mb=max(case.peak_rss_mb for case in case_results),
        review_rate=review_count / len(case_results),
        cases=tuple(case_results),
    )
