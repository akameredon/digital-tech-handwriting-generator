"""Verified character-to-image alignment for personalized handwriting fonts.

This module intentionally does not infer Unicode labels from x/y position,
connected-component order, or a fixed worksheet. A character observation can
enter a font only after its transcript and image region have been explicitly
confirmed by the teacher (or by a future audited review workflow).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import numpy as np

BBox = Tuple[int, int, int, int]
AUTO_CONFIRM_CONFIDENCE = 0.98


class GlyphAlignmentError(ValueError):
    """A recognition result cannot be safely aligned to image evidence."""


@dataclass(frozen=True)
class CharacterObservation:
    char: str
    bbox: BBox
    confidence: float
    provenance: str
    confirmed: bool
    image: np.ndarray

    def __post_init__(self) -> None:
        if len(self.char) != 1 or self.char.isspace():
            raise GlyphAlignmentError("Each observation must represent exactly one visible character.")
        x, y, width, height = self.bbox
        if min(x, y) < 0 or width < 1 or height < 1:
            raise GlyphAlignmentError("Character bounds must be positive page coordinates.")
        if not 0.0 <= self.confidence <= 1.0:
            raise GlyphAlignmentError("Character confidence must be between 0 and 1.")
        if self.provenance not in {"recognizer", "teacher_corrected", "teacher_drawn"}:
            raise GlyphAlignmentError("Unknown character evidence provenance.")
        if self.image is None or not isinstance(self.image, np.ndarray) or self.image.size == 0:
            raise GlyphAlignmentError("A character observation must include its source image crop.")
        if not self.confirmed and self.provenance != "recognizer":
            raise GlyphAlignmentError("Teacher-supplied evidence must be explicitly confirmed.")


def align_character_boxes(
    line_image: np.ndarray,
    recognized_text: str,
    boxes: Sequence[Sequence[int]],
    confidences: Sequence[float] | None = None,
    *,
    teacher_confirmed: bool = False,
) -> List[CharacterObservation]:
    """Bind provider-supplied character boxes to a reviewed line transcription.

    The recognizer must provide one box for each non-whitespace character.
    This function never creates boxes from character order or equal-width guesses.
    """
    if line_image is None or not isinstance(line_image, np.ndarray) or line_image.ndim not in (2, 3):
        raise GlyphAlignmentError("The source line image is invalid.")
    chars = [char for char in recognized_text if not char.isspace()]
    if not chars:
        raise GlyphAlignmentError("The transcription contains no visible characters.")
    if len(boxes) != len(chars):
        raise GlyphAlignmentError(
            f"Cannot align {len(chars)} visible characters to {len(boxes)} image regions. "
            "The recognizer must provide character-level boxes or the teacher must correct the alignment."
        )
    if confidences is not None and len(confidences) != len(chars):
        raise GlyphAlignmentError("Character confidence count does not match the transcription.")
    height, width = line_image.shape[:2]
    observations: List[CharacterObservation] = []
    for index, (char, raw_box) in enumerate(zip(chars, boxes)):
        if len(raw_box) != 4:
            raise GlyphAlignmentError(f"Character region {index + 1} is not an x, y, width, height box.")
        x, y, box_width, box_height = (int(value) for value in raw_box)
        if x < 0 or y < 0 or box_width < 1 or box_height < 1 or x + box_width > width or y + box_height > height:
            raise GlyphAlignmentError(f"Character region {index + 1} falls outside the source line image.")
        confidence = float(confidences[index]) if confidences is not None else 0.0
        if not 0.0 <= confidence <= 1.0:
            raise GlyphAlignmentError(f"Character confidence {index + 1} is outside [0, 1].")
        crop = line_image[y:y + box_height, x:x + box_width].copy()
        confirmed = bool(teacher_confirmed)
        observations.append(CharacterObservation(
            char=char,
            bbox=(x, y, box_width, box_height),
            confidence=confidence,
            provenance="teacher_corrected" if confirmed else "recognizer",
            confirmed=confirmed,
            image=crop,
        ))
    return observations


def confirm_observation(observation: CharacterObservation, corrected_char: str | None = None) -> CharacterObservation:
    """Teacher confirmation is explicit; optional correction changes only the label."""
    char = corrected_char if corrected_char is not None else observation.char
    return CharacterObservation(
        char=char,
        bbox=observation.bbox,
        confidence=observation.confidence,
        provenance="teacher_corrected",
        confirmed=True,
        image=observation.image.copy(),
    )


def confirmed_glyphs(observations: Iterable[CharacterObservation]) -> List[Dict[str, Any]]:
    """Return only confirmed, source-backed glyphs; preserve multiple variants."""
    result: List[Dict[str, Any]] = []
    for item in observations:
        if not item.confirmed:
            continue
        result.append({
            "label": item.char,
            "image": item.image.copy(),
            "bbox": item.bbox,
            "confidence": item.confidence,
            "provenance": item.provenance,
            "confirmed": True,
            "row": 1,
        })
    return result


def coverage_report(observations: Iterable[CharacterObservation], required_text: str = "") -> Dict[str, Any]:
    items = list(observations)
    confirmed = {item.char for item in items if item.confirmed}
    uncertain = {item.char for item in items if not item.confirmed}
    required = {char for char in required_text if not char.isspace()}
    return {
        "confirmed_characters": sorted(confirmed),
        "uncertain_characters": sorted(uncertain),
        "missing_characters": sorted(required - confirmed),
        "confirmed_count": len(confirmed),
        "uncertain_count": len(uncertain),
    }
