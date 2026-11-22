"""Page and handwriting segmentation for ordinary notebook photographs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np


BBox = Tuple[int, int, int, int]


@dataclass(frozen=True)
class PageBoundary:
    bbox: BBox
    confidence: float
    detected: bool


@dataclass(frozen=True)
class TextRegion:
    index: int
    bbox: BBox
    line_index: int
    paragraph_index: int
    ink_ratio: float

    def public_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "bbox": list(self.bbox),
            "line_index": self.line_index,
            "paragraph_index": self.paragraph_index,
            "ink_ratio": round(self.ink_ratio, 5),
        }


@dataclass
class SegmentationResult:
    width: int
    height: int
    page: PageBoundary
    lines: List[BBox]
    paragraphs: List[List[int]]
    regions: List[TextRegion]
    warnings: List[str]

    def public_dict(self) -> Dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "page": {"bbox": list(self.page.bbox), "confidence": round(self.page.confidence, 4), "detected": self.page.detected},
            "line_count": len(self.lines),
            "lines": [list(box) for box in self.lines],
            "paragraphs": self.paragraphs,
            "regions": [region.public_dict() for region in self.regions],
            "warnings": self.warnings,
        }


class NotebookSegmenter:
    """Segment a page without assuming a fixed worksheet or row count."""

    def __init__(self, min_line_height: int = 4, min_ink_pixels: int = 20):
        self.min_line_height = min_line_height
        self.min_ink_pixels = min_ink_pixels

    @staticmethod
    def _gray(image: np.ndarray) -> np.ndarray:
        if image is None or np.asarray(image).size == 0:
            raise ValueError("The notebook image is empty.")
        array = np.asarray(image)
        if array.ndim == 3:
            array = cv2.cvtColor(array, cv2.COLOR_BGR2GRAY)
        return array.astype(np.uint8, copy=False)

    @staticmethod
    def _ink(gray: np.ndarray) -> np.ndarray:
        enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        # Remove long notebook rules while keeping handwriting strokes.
        horizontal = cv2.getStructuringElement(cv2.MORPH_RECT, (max(35, gray.shape[1] // 14), 1))
        rules = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal)
        binary = cv2.subtract(binary, rules)
        return cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))

    @staticmethod
    def _page_boundary(gray: np.ndarray, ink: np.ndarray) -> PageBoundary:
        h, w = gray.shape[:2]
        # Strong page edges are lighter/darker transitions enclosing the largest area.
        edges = cv2.Canny(gray, 40, 140)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []
        for contour in contours:
            x, y, width, height = cv2.boundingRect(contour)
            area = width * height
            if width >= w * .45 and height >= h * .45:
                candidates.append((area, (x, y, width, height)))
        if candidates:
            area, box = max(candidates)
            confidence = min(1.0, area / (w * h * .85))
            return PageBoundary(box, confidence, True)
        # A clean crop is still a valid page; preserve full source coordinates.
        return PageBoundary((0, 0, w, h), 0.45, False)

    def _line_boxes(self, ink: np.ndarray) -> List[BBox]:
        projection = np.count_nonzero(ink, axis=1)
        active = projection >= max(2, int(ink.shape[1] * .001))
        runs: List[List[int]] = []
        start = None
        for y, on in enumerate(active):
            if on and start is None:
                start = y
            elif not on and start is not None:
                if y - start >= self.min_line_height:
                    runs.append([start, y])
                start = None
        if start is not None and ink.shape[0] - start >= self.min_line_height:
            runs.append([start, ink.shape[0]])
        # Merge detached dots and accents into their writing line.
        merged: List[List[int]] = []
        for top, bottom in runs:
            if merged and top - merged[-1][1] <= max(8, int(ink.shape[0] * .01)):
                merged[-1][1] = bottom
            else:
                merged.append([top, bottom])
        boxes = []
        for top, bottom in merged:
            xs = np.where(np.count_nonzero(ink[top:bottom], axis=0) > 0)[0]
            if len(xs):
                boxes.append((max(0, int(xs[0]) - 8), max(0, top - 5), min(ink.shape[1], int(xs[-1]) + 9) - max(0, int(xs[0]) - 8), min(ink.shape[0], bottom + 5) - max(0, top - 5)))
        return boxes

    @staticmethod
    def _paragraphs(lines: List[BBox], gap_factor: float = 1.9) -> List[List[int]]:
        if not lines:
            return []
        heights = [box[3] for box in lines]
        typical = float(np.median(heights))
        groups: List[List[int]] = [[0]]
        for index in range(1, len(lines)):
            previous = lines[index - 1]
            current = lines[index]
            gap = current[1] - (previous[1] + previous[3])
            if gap > typical * gap_factor:
                groups.append([index])
            else:
                groups[-1].append(index)
        return groups

    def _regions(self, ink: np.ndarray, lines: List[BBox], paragraphs: List[List[int]]) -> List[TextRegion]:
        paragraph_for_line = {line: paragraph for paragraph, group in enumerate(paragraphs) for line in group}
        regions: List[TextRegion] = []
        for line_index, (x, y, width, height) in enumerate(lines):
            crop = ink[y:y + height, x:x + width]
            columns = np.count_nonzero(crop, axis=0)
            active = columns > 0
            runs: List[List[int]] = []
            start = None
            for col, on in enumerate(active):
                if on and start is None: start = col
                elif not on and start is not None:
                    if col - start >= 2: runs.append([start, col])
                    start = None
            if start is not None: runs.append([start, len(active)])
            # Merge close components into text regions; preserve larger gaps as word/phrase breaks.
            merged: List[List[int]] = []
            for left, right in runs:
                if merged and left - merged[-1][1] <= max(5, int(width * .012)):
                    merged[-1][1] = right
                else:
                    merged.append([left, right])
            for left, right in merged:
                region = crop[:, left:right]
                ink_ratio = float(np.count_nonzero(region) / max(1, region.size))
                regions.append(TextRegion(len(regions), (x + left, y, right - left, height), line_index, paragraph_for_line.get(line_index, 0), ink_ratio))
        return regions

    def segment(self, image: np.ndarray) -> SegmentationResult:
        gray = self._gray(image)
        ink = self._ink(gray)
        if int(cv2.countNonZero(ink)) < self.min_ink_pixels:
            raise ValueError("Not enough handwriting was found to segment this page.")
        page = self._page_boundary(gray, ink)
        lines = self._line_boxes(ink)
        if not lines:
            raise ValueError("No writing lines were detected on this page.")
        paragraphs = self._paragraphs(lines)
        regions = self._regions(ink, lines, paragraphs)
        warnings: List[str] = []
        if not page.detected:
            warnings.append("No strong page boundary was detected; full image coordinates were retained.")
        if len(lines) == 1:
            warnings.append("Only one writing line was detected; paragraph grouping is limited.")
        return SegmentationResult(gray.shape[1], gray.shape[0], page, lines, paragraphs, regions, warnings)
