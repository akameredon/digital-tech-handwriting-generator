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
        if "verified" not in source and "worksheet_cell" not in source:
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
