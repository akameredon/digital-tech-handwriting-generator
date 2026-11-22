"""Bridge HTR output into safe, reviewable glyph evidence.

This module intentionally does not infer character boxes. It coordinates the
existing page analysis, HTR result, and CharacterAligner contracts so a future
geometry-aware recognizer can be plugged in without bypassing review gates.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from ingestion.open_handwriting import PageAnalysis
from model.character_alignment import CharacterAligner, RecognitionAlignmentResult
from model.htr import HTRDocumentResult


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
