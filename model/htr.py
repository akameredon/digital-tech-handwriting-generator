"""Handwritten-text recognition orchestration with honest confidence handling.

The pipeline is model-agnostic: a real HTR provider is injected, then outputs are
normalized, calibrated, checked for ambiguity, and tied back to source line boxes.
It never turns a missing provider into guessed text.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple

import numpy as np

from ingestion.open_handwriting import PageAnalysis, RecognitionUnavailable


class HTRProvider(Protocol):
    name: str

    def recognize_lines(self, lines: Sequence[np.ndarray]) -> Sequence[Dict[str, Any]]:
        """Return one mapping per line: text, confidence, optional alternatives."""


@dataclass(frozen=True)
class HTRLineResult:
    line_index: int
    bbox: Tuple[int, int, int, int]
    text: str
    confidence: float
    alternatives: Tuple[str, ...]
    needs_review: bool
    review_reasons: Tuple[str, ...]
    provider: str
    character_boxes: Tuple[Dict[str, Any], ...] = ()

    def public_dict(self) -> Dict[str, Any]:
        return {
            "line_index": self.line_index,
            "bbox": list(self.bbox),
            "text": self.text,
            "confidence": round(self.confidence, 4),
            "alternatives": list(self.alternatives),
            "needs_review": self.needs_review,
            "review_reasons": list(self.review_reasons),
            "provider": self.provider,
            "character_boxes": [dict(box) for box in self.character_boxes],
        }


@dataclass
class HTRDocumentResult:
    lines: List[HTRLineResult]
    provider: str
    warnings: List[str]

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

    @property
    def needs_review(self) -> bool:
        return any(line.needs_review for line in self.lines)

    def public_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "provider": self.provider,
            "needs_review": self.needs_review,
            "warnings": self.warnings,
            "lines": [line.public_dict() for line in self.lines],
        }


class HTRPipeline:
    """Run an injected recognizer and make its uncertainty actionable."""

    def __init__(self, provider: Optional[HTRProvider] = None, review_threshold: float = 0.85):
        self.provider = provider
        self.review_threshold = review_threshold

    @staticmethod
    def _clean_text(value: Any) -> str:
        text = unicodedata.normalize("NFKC", str(value or ""))
        text = "".join(
            char if char == "\n" or unicodedata.category(char) != "Cc" else " "
            for char in text
        )
        return re.sub(r"[ \t]+", " ", text).strip()

    @staticmethod
    def _confidence(value: Any) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.0
        # Accept either a probability or a percentage from provider adapters.
        if score > 1.0:
            score /= 100.0
        return max(0.0, min(1.0, score))

    @staticmethod
    def _alternatives(value: Any, text: str) -> Tuple[str, ...]:
        if not isinstance(value, (list, tuple)):
            return ()
        seen = []
        for candidate in value:
            normalized = HTRPipeline._clean_text(candidate)
            if normalized and normalized != text and normalized not in seen:
                seen.append(normalized)
        return tuple(seen[:5])

    @staticmethod
    def _character_boxes(value: Any) -> Tuple[Dict[str, Any], ...]:
        """Preserve explicit provider geometry for the alignment stage.

        Malformed entries are retained as ``{"bbox": None}`` so the
        downstream aligner can produce a localized review reason. Dropping an
        entry here would turn a geometry mismatch into a dangerous positional
        re-indexing opportunity.
        """
        if not isinstance(value, (list, tuple)):
            return ()
        boxes: List[Dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                box = dict(item)
            elif isinstance(item, (list, tuple)) and len(item) == 4:
                box = {"bbox": list(item)}
            else:
                box = {"bbox": None}
            if "bbox" in box and isinstance(box["bbox"], tuple):
                box["bbox"] = list(box["bbox"])
            boxes.append(box)
        return tuple(boxes)

    def recognize(self, analysis: PageAnalysis) -> HTRDocumentResult:
        if self.provider is None:
            raise RecognitionUnavailable(
                "Handwriting recognition is not configured. Install or connect an HTR provider before generating text."
            )
        raw_results = list(self.provider.recognize_lines([line.crop for line in analysis.lines]))
        if len(raw_results) != len(analysis.lines):
            raise RuntimeError("The HTR provider returned a different number of results than detected lines.")
        provider_name = str(getattr(self.provider, "name", self.provider.__class__.__name__))
        results: List[HTRLineResult] = []
        for region, raw in zip(analysis.lines, raw_results):
            if not isinstance(raw, dict):
                raise TypeError("Each HTR result must be a mapping with text and confidence fields.")
            text = self._clean_text(raw.get("text"))
            confidence = self._confidence(raw.get("confidence"))
            alternatives = self._alternatives(raw.get("alternatives"), text)
            character_boxes = self._character_boxes(raw.get("character_boxes", raw.get("char_boxes")))
            reasons: List[str] = []
            if not text:
                reasons.append("empty recognition")
            if confidence < self.review_threshold:
                reasons.append(f"confidence below {self.review_threshold:.2f}")
            if alternatives:
                reasons.append("competing alternatives returned")
            # Provider may surface a character-level ambiguity map.
            ambiguous = raw.get("ambiguous_characters", [])
            if ambiguous:
                reasons.append("ambiguous characters: " + ", ".join(map(str, ambiguous)))
            if raw.get("character_geometry_mismatch"):
                reasons.append("character geometry count mismatch")
            expected_characters = len([character for character in text if not character.isspace()])
            if character_boxes and len(character_boxes) != expected_characters:
                reasons.append("character geometry count mismatch")
            results.append(HTRLineResult(
                line_index=region.index,
                bbox=tuple(region.bbox),
                text=text,
                confidence=confidence,
                alternatives=alternatives,
                needs_review=bool(reasons),
                review_reasons=tuple(reasons),
                provider=provider_name,
                character_boxes=character_boxes,
            ))
        warnings: List[str] = []
        if any(line.needs_review for line in results):
            warnings.append("One or more lines need teacher review before their text is used for lesson generation.")
        return HTRDocumentResult(results, provider_name, warnings)
