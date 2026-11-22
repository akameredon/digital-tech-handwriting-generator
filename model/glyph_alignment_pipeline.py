"""Bridge HTR output into safe, reviewable glyph evidence.

This module intentionally does not infer character boxes. It coordinates the
existing page analysis, HTR result, and CharacterAligner contracts so a future
geometry-aware recognizer can be plugged in without bypassing review gates.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np

from ingestion.open_handwriting import PageAnalysis
from model.character_alignment import AlignmentResult, CharacterAligner, CharacterAlignmentError, RecognitionAlignmentResult
from model.htr import HTRDocumentResult
from model.writer_style import StyleLearningResult, VerifiedGlyphSample, WriterStyleLearner


@dataclass
class DocumentGlyphAlignment:
    """Per-line alignment results plus document-level warnings."""

    lines: List[RecognitionAlignmentResult]
    warnings: List[str]

    @property
    def candidates(self):
        return [candidate for result in self.lines for candidate in result.candidates]

    @property
    def needs_review(self) -> bool:
        return bool(self.warnings) or any(result.review for result in self.lines)

    def public_dict(self) -> Dict[str, Any]:
        return {
            "line_count": len(self.lines),
            "candidate_count": len(self.candidates),
            "needs_review": self.needs_review,
            "warnings": self.warnings,
            "lines": [result.public_dict() for result in self.lines],
        }


def align_document_glyphs(
    analysis: PageAnalysis,
    recognition: HTRDocumentResult,
    *,
    aligner: CharacterAligner | None = None,
    confidence_threshold: float = 0.85,
) -> DocumentGlyphAlignment:
    """Align only provider-supplied character geometry to source line crops.

    A missing geometry payload becomes a localized review result. The function
    never pairs a transcript with connected components by order or x-position.
    """
    if len(analysis.lines) != len(recognition.lines):
        raise ValueError("Page analysis and HTR result contain different line counts.")
    character_aligner = aligner or CharacterAligner()
    results: List[RecognitionAlignmentResult] = []
    warnings: List[str] = []
    for region, line in zip(analysis.lines, recognition.lines):
        line_evidence = {"text": line.text}
        if line.character_boxes:
            line_evidence["character_boxes"] = list(line.character_boxes)
        result = character_aligner.align_recognized_line(
            region.crop,
            tuple(region.bbox),
            line_evidence,
            confidence_threshold=confidence_threshold,
        )
        results.append(result)
        if result.review:
            warnings.append(f"Line {line.line_index} requires glyph review before profile updates.")
    return DocumentGlyphAlignment(results, warnings)


def confirm_document_glyphs(
    alignment: DocumentGlyphAlignment,
    confirmations: Dict[str, str],
    *,
    source_width: int,
    source_height: int,
    aligner: CharacterAligner | None = None,
) -> AlignmentResult:
    """Promote only explicitly confirmed candidates across all page lines.

    ``confirmations`` is keyed by ``"line_index:candidate_index"``. The key
    makes the browser payload stable and prevents a client from confirming a
    candidate by an inferred character position. Unmentioned or mismatched
    candidates remain pending and are not added to the writer profile.
    """
    character_aligner = aligner or CharacterAligner()
    observations = []
    warnings: List[str] = []
    for line_number, result in enumerate(alignment.lines):
        labels = {
            index: confirmations[key]
            for index in range(len(result.candidates))
            if (key := f"{line_number}:{index}") in confirmations
        }
        if not labels:
            continue
        try:
            confirmed = character_aligner.confirm_candidates(
                result.candidates,
                labels,
                source_width=source_width,
                source_height=source_height,
            )
        except CharacterAlignmentError as exc:
            warnings.append(f"Line {line_number} confirmations were rejected: {exc}")
            continue
        observations.extend(confirmed.observations)
        warnings.extend(confirmed.warnings)
    if not observations:
        raise ValueError("No character candidates were explicitly confirmed.")
    return AlignmentResult(observations=observations, warnings=warnings)


def learn_writer_profile(
    confirmed: AlignmentResult,
    *,
    writer_name: str,
    learner: WriterStyleLearner | None = None,
) -> StyleLearningResult:
    """Convert trusted observations into the existing reusable profile learner."""
    samples = [
        VerifiedGlyphSample(
            label=observation.label,
            # CharacterAligner stores normalized white-ink masks. Convert to
            # the learner's dark-ink convention and add context lost by a
            # tight crop so a solid glyph is not mistaken for a blank image.
            image=np.pad(255 - observation.image, 6, mode="constant", constant_values=255),
            confidence=observation.quality,
            source=observation.source,
        )
        for observation in confirmed.observations
    ]
    return (learner or WriterStyleLearner(min_confidence=0.55)).fit(samples, writer_name=writer_name)
