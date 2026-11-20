"""Open-layout handwriting intake and pluggable HTR contract.

This module deliberately does not infer Unicode labels from glyph position.
It analyzes natural pages and returns line regions for a handwriting recognizer.
Until a real HTR provider is configured, callers must report recognition as
unavailable rather than silently compiling a falsely labelled font.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple

import cv2
import numpy as np


class HandwritingIntakeError(ValueError):
    """The uploaded page cannot be analyzed as a usable image."""


@dataclass
class TextLineRegion:
    index: int
    bbox: Tuple[int, int, int, int]
    crop: np.ndarray
    ink_ratio: float


@dataclass
class PageAnalysis:
    width: int
    height: int
    quality: str
    warnings: List[str]
    lines: List[TextLineRegion]

    def public_dict(self) -> Dict[str, Any]:
        return {
            "width": self.width, "height": self.height,
            "quality": self.quality, "warnings": self.warnings,
            "line_count": len(self.lines),
            "lines": [
                {"index": line.index, "bbox": list(line.bbox),
                 "ink_ratio": round(line.ink_ratio, 4)}
                for line in self.lines
            ],
        }


class HandwritingRecognizer(Protocol):
    """Adapter contract for genuine HTR with optional character-level geometry."""
    name: str

    def recognize_lines(self, lines: Sequence[np.ndarray]) -> List[Dict[str, Any]]:
        """Return text, confidence, and (when supported) per-character boxes."""


class RecognitionUnavailable(RuntimeError):
    pass


class OpenHandwritingIntake:
    """Analyze ordinary handwritten pages without fixed rows or character order."""

    def __init__(self, min_dimension: int = 180, min_ink_pixels: int = 80):
        self.min_dimension = min_dimension
        self.min_ink_pixels = min_ink_pixels

    def load(self, image_path: str | Path) -> np.ndarray:
        path = Path(image_path)
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None or image.size == 0:
            raise HandwritingIntakeError("We could not read this image. Choose a clear JPG or PNG photo.")
        h, w = image.shape[:2]
        if min(h, w) < self.min_dimension:
            raise HandwritingIntakeError("This image is too small. Upload a higher-resolution photo of your handwriting.")
        return image

    @staticmethod
    def _remove_page_rules(binary: np.ndarray) -> np.ndarray:
        horizontal = cv2.getStructuringElement(cv2.MORPH_RECT, (max(35, binary.shape[1] // 16), 1))
        rules = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal, iterations=1)
        return cv2.subtract(binary, rules)

    def analyze(self, image_path: str | Path) -> PageAnalysis:
        image = self.load(image_path)
        height, width = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        binary = self._remove_page_rules(binary)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)), iterations=1)
        if int(cv2.countNonZero(binary)) < self.min_ink_pixels:
            raise HandwritingIntakeError("We could not find enough visible handwriting. Try a closer, clearer photo.")

        # Horizontal projection groups ink into natural text-line bands. It does
        # not assume a number of rows, character order, or one glyph per component.
        projection = np.count_nonzero(binary, axis=1)
        threshold = max(2, int(width * 0.0008))
        active = projection >= threshold
        runs: List[List[int]] = []
        start: Optional[int] = None
        for y, value in enumerate(active):
            if value and start is None:
                start = y
            elif not value and start is not None:
                if y - start >= 2:
                    runs.append([start, y])
                start = None
        if start is not None and height - start >= 2:
            runs.append([start, height])

        # Merge nearby bands so detached dots and accents stay with their line.
        merged: List[List[int]] = []
        for top, bottom in runs:
            if merged and top - merged[-1][1] <= max(8, int(height * 0.008)):
                merged[-1][1] = bottom
            else:
                merged.append([top, bottom])

        lines: List[TextLineRegion] = []
        for top, bottom in merged:
            region = binary[top:bottom, :]
            xs = np.where(np.count_nonzero(region, axis=0) > 0)[0]
            if len(xs) == 0:
                continue
            left, right = max(0, int(xs[0]) - 8), min(width, int(xs[-1]) + 9)
            pad_y = max(4, int((bottom - top) * 0.12))
            y0, y1 = max(0, top - pad_y), min(height, bottom + pad_y)
            crop = gray[y0:y1, left:right].copy()
            line_ink = int(cv2.countNonZero(binary[y0:y1, left:right]))
            area = max(1, crop.shape[0] * crop.shape[1])
            lines.append(TextLineRegion(len(lines), (left, y0, right-left, y1-y0), crop, line_ink / area))

        if not lines:
            raise HandwritingIntakeError("We could not detect handwriting lines in this image.")
        warnings: List[str] = []
        if len(lines) < 2:
            warnings.append("Only one text line was detected; more handwriting may improve style coverage.")
        if width > height * 1.8:
            warnings.append("This is a wide image. Check that the full page is visible.")
        quality = "usable" if len(lines) >= 2 else "limited"
        return PageAnalysis(width, height, quality, warnings, lines)


class ConfiguredRecognizer:
    """Resolve a recognizer adapter only when a supported model is configured.

    The adapter is intentionally injected by the application. No model is
    downloaded implicitly and no paid external API is called.
    """
    def __init__(self, provider: Optional[HandwritingRecognizer] = None):
        self.provider = provider

    @property
    def available(self) -> bool:
        return self.provider is not None

    def recognize(self, analysis: PageAnalysis) -> List[Dict[str, Any]]:
        if self.provider is None:
            raise RecognitionUnavailable(
                "Handwriting recognition is not configured on this server yet. Your image was accepted, but font generation is not available until the recognition model is installed."
            )
        results = self.provider.recognize_lines([line.crop for line in analysis.lines])
        if len(results) != len(analysis.lines):
            raise RuntimeError("The handwriting recognizer returned an unexpected number of line results.")
        normalized = []
        for line, result in zip(analysis.lines, results):
            text = str(result.get("text", ""))
            confidence = float(result.get("confidence", 0.0))
            visible_count = len([char for char in text if not char.isspace()])
            raw_boxes = result.get("char_boxes", [])
            raw_char_confidences = result.get("char_confidences", [])
            # Character geometry is accepted only when every visible character
            # has a matching model-supplied region. No equal-width guesswork.
            char_boxes = raw_boxes if len(raw_boxes) == visible_count else []
            char_confidences = (
                raw_char_confidences
                if char_boxes and len(raw_char_confidences) == visible_count
                else ([0.0] * visible_count if char_boxes else [])
            )
            normalized.append({
                "line_index": line.index, "bbox": list(line.bbox),
                "text": text, "confidence": max(0.0, min(1.0, confidence)),
                "char_boxes": char_boxes,
                "char_confidences": char_confidences,
                "provider": str(result.get("provider", getattr(self.provider, "name", "unknown"))),
                "needs_review": confidence < 0.85 or not char_boxes,
            })
        return normalized