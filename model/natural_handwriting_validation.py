"""Dataset-driven validation for natural handwriting pages.

This module deliberately separates engineering readiness from model quality. It
can run against synthetic fixtures in CI and real labelled teacher pages when a
manifest is supplied, but it never treats missing real data as a passing gate.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Sequence

from ingestion.open_handwriting import OpenHandwritingIntake, PageAnalysis
from model.glyph_alignment_pipeline import DocumentGlyphAlignment, align_document_glyphs
from model.htr import HTRDocumentResult, HTRPipeline
from model.htr_benchmark import character_error_rate, word_error_rate


@dataclass(frozen=True)
class NaturalPageCase:
    image_path: str
    reference_text: str
    case_id: str = ""
    real_data: bool = True


@dataclass(frozen=True)
class NaturalPageCaseResult:
    case_id: str
    image_path: str
    reference_text: str
    recognized_text: str
    line_count: int
    character_error_rate: float
    word_error_rate: float
    needs_review: bool
    review_line_count: int
    candidate_count: int
    geometry_review_count: int
    passed: bool


@dataclass(frozen=True)
class NaturalPageValidationReport:
    provider: str
    case_count: int
    mean_character_error_rate: float
    mean_word_error_rate: float
    page_review_rate: float
    geometry_candidate_rate: float
    real_data: bool
    passed: bool
    cases: tuple[NaturalPageCaseResult, ...]

    def public_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["cases"] = [asdict(case) for case in self.cases]
        return data


def load_cases(path: str | Path) -> list[NaturalPageCase]:
    """Load a JSONL manifest with image paths and human transcription text."""
    manifest = Path(path)
    cases: list[NaturalPageCase] = []
    for line_number, raw in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
            image_path = Path(str(item["image_path"]))
            if not image_path.is_absolute():
                image_path = manifest.parent / image_path
            reference = str(item["reference_text"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid natural-page case on line {line_number}.") from exc
        cases.append(NaturalPageCase(
            str(image_path),
            reference,
            str(item.get("case_id", line_number)),
            bool(item.get("real_data", True)),
        ))
    if not cases:
        raise ValueError("The natural-page manifest contains no cases.")
    return cases


def _line_review_count(recognition: HTRDocumentResult) -> int:
    return sum(line.needs_review for line in recognition.lines)


def validate_pages(
    provider: Any,
    cases: Iterable[NaturalPageCase],
    *,
    intake_factory: Callable[[], OpenHandwritingIntake] = OpenHandwritingIntake,
    max_cer: float = 0.10,
    max_wer: float = 0.20,
) -> NaturalPageValidationReport:
    """Evaluate labelled natural pages through the complete production bridge."""
    cases = list(cases)
    if not cases:
        raise ValueError("At least one natural-page case is required for validation.")
    results: list[NaturalPageCaseResult] = []
    for case in cases:
        analysis: PageAnalysis = intake_factory().analyze(case.image_path)
        recognition = HTRPipeline(provider).recognize(analysis)
        alignment: DocumentGlyphAlignment = align_document_glyphs(analysis, recognition)
        cer = character_error_rate(case.reference_text, recognition.text)
        wer = word_error_rate(case.reference_text, recognition.text)
        review_lines = _line_review_count(recognition)
        geometry_review_count = sum(len(line.review) for line in alignment.lines)
        passed = cer <= max_cer and wer <= max_wer and not alignment.needs_review
        results.append(NaturalPageCaseResult(
            case_id=case.case_id,
            image_path=case.image_path,
            reference_text=case.reference_text,
            recognized_text=recognition.text,
            line_count=len(analysis.lines),
            character_error_rate=round(cer, 4),
            word_error_rate=round(wer, 4),
            needs_review=recognition.needs_review or alignment.needs_review,
            review_line_count=review_lines,
            candidate_count=len(alignment.candidates),
            geometry_review_count=geometry_review_count,
            passed=passed,
        ))

    count = len(results)
    return NaturalPageValidationReport(
        provider=str(getattr(provider, "name", provider.__class__.__name__)),
        case_count=count,
        mean_character_error_rate=sum(case.character_error_rate for case in results) / count,
        mean_word_error_rate=sum(case.word_error_rate for case in results) / count,
        page_review_rate=sum(case.needs_review for case in results) / count,
        geometry_candidate_rate=sum(case.candidate_count > 0 for case in results) / count,
        real_data=all(case.real_data for case in cases),
        passed=bool(results) and all(case.passed for case in results),
        cases=tuple(results),
    )
