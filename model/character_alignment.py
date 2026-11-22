"""Verified character extraction, alignment, and quality metadata.

This module keeps character evidence traceable: every aligned character retains its
label source, source position, sequence index, normalized crop, and a quality score.
It never guesses labels from a character's position alone.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import cv2
import numpy as np


class CharacterAlignmentError(ValueError):
    """A character sample cannot be safely aligned."""


@dataclass(frozen=True)
class CharacterObservation:
    label: str
    sequence_index: int
    source: str
    source_bbox: Tuple[int, int, int, int]
    normalized_bbox: Tuple[float, float, float, float]
    quality: float
    ink_ratio: float
    component_count: int
    touches_border: bool
    image: np.ndarray

    def public_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("image", None)
        data["source_bbox"] = list(self.source_bbox)
        data["normalized_bbox"] = [round(v, 5) for v in self.normalized_bbox]
        data["quality"] = round(self.quality, 4)
        data["ink_ratio"] = round(self.ink_ratio, 5)
        return data


@dataclass
class AlignmentResult:
    observations: List[CharacterObservation]
    warnings: List[str]

    @property
    def accepted(self) -> List[CharacterObservation]:
        return [item for item in self.observations if item.quality >= 0.55]

    def public_dict(self) -> Dict[str, Any]:
        return {
            "count": len(self.observations),
            "accepted_count": len(self.accepted),
            "warnings": self.warnings,
            "characters": [item.public_dict() for item in self.observations],
        }


@dataclass(frozen=True)
class CharacterCandidate:
    """A model-produced glyph candidate that is not trusted yet.

    A candidate is evidence for a possible Unicode label, not a confirmed
    observation.  Keeping this state separate prevents a plausible OCR result
    from contaminating a writer profile before a teacher or a stronger
    verification stage confirms it.
    """

    label: str
    source_bbox: Tuple[int, int, int, int]
    confidence: float
    image: np.ndarray
    source: str
    review_reasons: Tuple[str, ...] = ()

    def public_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "source_bbox": list(self.source_bbox),
            "confidence": round(self.confidence, 4),
            "source": self.source,
            "review_reasons": list(self.review_reasons),
        }


@dataclass
class RecognitionAlignmentResult:
    """Candidates and unresolved evidence returned by model-based alignment."""

    candidates: List[CharacterCandidate]
    review: List[Dict[str, Any]]
    warnings: List[str]

    @property
    def ready_for_confirmation(self) -> bool:
        return bool(self.candidates) and not self.review

    def public_dict(self) -> Dict[str, Any]:
        return {
            "candidate_count": len(self.candidates),
            "review_count": len(self.review),
            "candidates": [candidate.public_dict() for candidate in self.candidates],
            "review": self.review,
            "warnings": self.warnings,
        }


class CharacterAligner:
    """Align trusted labeled crops while retaining their origin and confidence."""

    def __init__(self, canvas_size: Tuple[int, int] = (96, 96), min_ink_pixels: int = 5):
        self.canvas_size = canvas_size
        self.min_ink_pixels = min_ink_pixels

    @staticmethod
    def _binary(image: np.ndarray) -> np.ndarray:
        array = np.asarray(image)
        if array.ndim == 3:
            array = cv2.cvtColor(array, cv2.COLOR_BGR2GRAY)
        if array.size == 0:
            raise CharacterAlignmentError("The character crop is empty.")
        if array.dtype != np.uint8:
            array = cv2.normalize(array, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        threshold = cv2.threshold(array, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        if cv2.countNonZero(threshold) < 5:
            # Also accept already-binary white ink on black crops.
            threshold = cv2.threshold(array, 127, 255, cv2.THRESH_BINARY)[1]
        return threshold

    def _one(self, sample: Mapping[str, Any], sequence_index: int) -> CharacterObservation:
        label = str(sample.get("label", ""))
        if len(label) != 1:
            raise CharacterAlignmentError("Every aligned character must have exactly one verified label.")
        image = self._binary(np.asarray(sample.get("image")))
        ys, xs = np.where(image > 0)
        if len(xs) < self.min_ink_pixels:
            raise CharacterAlignmentError(f"Character {label!r} has too little ink to align.")
        x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
        crop = image[y0:y1 + 1, x0:x1 + 1]
        h, w = image.shape[:2]
        ink_ratio = float(len(xs) / max(1, h * w))
        components, _, stats, _ = cv2.connectedComponentsWithStats(image, 8)
        component_count = max(0, components - 1)
        touches = x0 == 0 or y0 == 0 or x1 == w - 1 or y1 == h - 1
        # A quality score rewards readable ink and penalizes clipping, specks, and
        # excessive fill. It is a review signal, not a fabricated recognition score.
        density_score = min(1.0, ink_ratio / 0.12) if ink_ratio <= 0.12 else max(0.0, 1.0 - (ink_ratio - 0.12) / 0.35)
        size_score = min(1.0, max(w, h) / 18.0)
        component_score = 1.0 if component_count <= 3 else max(0.25, 1.0 - .12 * (component_count - 3))
        quality = max(0.0, min(1.0, .45 * density_score + .25 * size_score + .20 * component_score + .10 * (not touches)))
        normalized = cv2.resize(crop, self.canvas_size, interpolation=cv2.INTER_AREA)
        bbox = sample.get("bbox")
        if bbox is None:
            bbox = (x0, y0, x1 - x0 + 1, y1 - y0 + 1)
        source_bbox = tuple(int(v) for v in bbox)
        source_width = max(1, int(sample.get("source_width", w)))
        source_height = max(1, int(sample.get("source_height", h)))
        normalized_bbox = (source_bbox[0] / source_width, source_bbox[1] / source_height,
                           source_bbox[2] / source_width, source_bbox[3] / source_height)
        source = str(sample.get("label_source", sample.get("source", "unverified")))
        if all(token not in source for token in ("verified", "worksheet_cell", "teacher_confirmed")):
            raise CharacterAlignmentError(f"Label source for {label!r} is not verified.")
        return CharacterObservation(label, sequence_index, source, source_bbox, normalized_bbox,
                                    quality, ink_ratio, component_count, touches, normalized)

    def align(self, samples: Iterable[Mapping[str, Any]]) -> AlignmentResult:
        observations: List[CharacterObservation] = []
        warnings: List[str] = []
        for index, sample in enumerate(samples):
            try:
                observations.append(self._one(sample, index))
            except CharacterAlignmentError as exc:
                warnings.append(f"Skipped sequence item {index}: {exc}")
        if not observations:
            raise CharacterAlignmentError("No verifiable character samples could be aligned.")
        labels = [item.label for item in observations]
        duplicates = sorted({label for label in labels if labels.count(label) > 1})
        if duplicates:
            warnings.append("Repeated labels retained as variants: " + ", ".join(duplicates))
        return AlignmentResult(observations, warnings)

    @staticmethod
    def _recognition_characters(text: str) -> List[str]:
        """Return glyph-bearing characters while keeping spaces out of crops."""
        return [character for character in str(text) if not character.isspace()]

    @staticmethod
    def _box(value: Any) -> Optional[Tuple[int, int, int, int]]:
        if isinstance(value, Mapping):
            value = value.get("bbox")
        if not isinstance(value, (list, tuple)) or len(value) != 4:
            return None
        try:
            x, y, width, height = (int(item) for item in value)
        except (TypeError, ValueError):
            return None
        return x, y, width, height

    def align_recognized_line(
        self,
        line_image: np.ndarray,
        line_bbox: Tuple[int, int, int, int],
        recognition: Mapping[str, Any],
        *,
        confidence_threshold: float = 0.85,
    ) -> RecognitionAlignmentResult:
        """Convert explicit model character boxes into reviewable candidates.

        The recognizer must provide one box per non-whitespace character under
        ``character_boxes`` (or ``char_boxes``).  A line transcript without
        these boxes is intentionally insufficient: assigning boxes by order or
        x-position would recreate the unsafe historical behavior.
        """
        array = np.asarray(line_image)
        if array.size == 0:
            raise CharacterAlignmentError("The recognized line image is empty.")
        if array.ndim == 3:
            array = cv2.cvtColor(array, cv2.COLOR_BGR2GRAY)
        text = str(recognition.get("text", ""))
        labels = self._recognition_characters(text)
        raw_boxes = recognition.get("character_boxes", recognition.get("char_boxes"))
        if raw_boxes is None:
            return RecognitionAlignmentResult(
                candidates=[],
                review=[{"reason": "character_geometry_missing", "message": (
                    "The recognizer returned line text but no character geometry; "
                    "no glyph can be safely associated with a Unicode label."
                )}],
                warnings=["Line-level recognition is not sufficient for glyph extraction."],
            )
        boxes = list(raw_boxes) if isinstance(raw_boxes, (list, tuple)) else []
        if len(boxes) != len(labels):
            return RecognitionAlignmentResult(
                candidates=[],
                review=[{"reason": "character_geometry_count_mismatch", "expected": len(labels), "received": len(boxes)}],
                warnings=["Character geometry count does not match the recognized text."],
            )

        height, width = array.shape[:2]
        candidates: List[CharacterCandidate] = []
        review: List[Dict[str, Any]] = []
        for index, (label, raw_box) in enumerate(zip(labels, boxes)):
            bbox = self._box(raw_box)
            if bbox is None:
                review.append({"index": index, "label": label, "reason": "invalid_character_geometry"})
                continue
            x, y, box_width, box_height = bbox
            score = 0.0
            if isinstance(raw_box, Mapping):
                try:
                    score = float(raw_box.get("confidence", 0.0))
                except (TypeError, ValueError):
                    score = 0.0
                if score > 1.0:
                    score /= 100.0
            reasons: List[str] = []
            if box_width <= 0 or box_height <= 0 or x < 0 or y < 0 or x + box_width > width or y + box_height > height:
                reasons.append("character_geometry_out_of_bounds")
            if score < confidence_threshold:
                reasons.append(f"character_confidence_below_{confidence_threshold:.2f}")
            if reasons:
                review.append({"index": index, "label": label, "bbox": list(bbox), "reason": reasons})
                continue
            crop = array[y:y + box_height, x:x + box_width].copy()
            # Reject a blank white crop. Tight model boxes can legitimately
            # contain only dark ink, so a uniform-black crop is retained for
            # the downstream quality gate rather than discarded here.
            if crop.size == 0 or (int(crop.max()) == 255 and int(crop.min()) == 255):
                review.append({"index": index, "label": label, "reason": "empty_character_crop"})
                continue
            candidates.append(CharacterCandidate(
                label=label,
                source_bbox=(line_bbox[0] + x, line_bbox[1] + y, box_width, box_height),
                confidence=max(0.0, min(1.0, score)),
                image=crop,
                source="htr_character_geometry_pending_confirmation",
                review_reasons=(),
            ))
        if review:
            return RecognitionAlignmentResult(
                candidates=candidates,
                review=review,
                warnings=["Some character candidates require localized teacher review before use."],
            )
        return RecognitionAlignmentResult(candidates=candidates, review=[], warnings=[])

    def confirm_candidates(
        self,
        candidates: Iterable[CharacterCandidate],
        confirmed_labels: Mapping[int, str],
        *,
        source_width: int,
        source_height: int,
    ) -> AlignmentResult:
        """Promote only explicitly confirmed candidates into trusted evidence."""
        samples: List[Dict[str, Any]] = []
        for index, candidate in enumerate(candidates):
            confirmed = str(confirmed_labels.get(index, ""))
            if len(confirmed) != 1 or confirmed != candidate.label:
                continue
            samples.append({
                "label": confirmed,
                "image": candidate.image,
                "bbox": candidate.source_bbox,
                "source_width": source_width,
                "source_height": source_height,
                "label_source": "htr_character_geometry_teacher_confirmed",
            })
        if not samples:
            raise CharacterAlignmentError("No character candidates were explicitly confirmed.")
        return self.align(samples)
