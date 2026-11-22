"""Image correction that improves page geometry while preserving handwriting detail."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple

import cv2
import numpy as np


Point = Tuple[float, float]


@dataclass(frozen=True)
class PreservationReport:
    original_size: Tuple[int, int]
    output_size: Tuple[int, int]
    perspective_corrected: bool
    rotation_degrees: float
    illumination_normalized: bool
    detail_score_before: float
    detail_score_after: float
    warnings: Tuple[str, ...]

    def public_dict(self) -> Dict[str, Any]:
        return {
            "original_size": list(self.original_size),
            "output_size": list(self.output_size),
            "perspective_corrected": self.perspective_corrected,
            "rotation_degrees": round(self.rotation_degrees, 3),
            "illumination_normalized": self.illumination_normalized,
            "detail_score_before": round(self.detail_score_before, 5),
            "detail_score_after": round(self.detail_score_after, 5),
            "warnings": list(self.warnings),
        }


class HandwritingPreserver:
    """Correct capture defects conservatively, retaining a high-detail grayscale path."""

    def __init__(self, max_side: int = 2800):
        self.max_side = max_side

    @staticmethod
    def _validate(image: np.ndarray) -> np.ndarray:
        if image is None or np.asarray(image).size == 0:
            raise ValueError("The handwriting image is empty.")
        array = np.asarray(image)
        if array.ndim == 2:
            array = cv2.cvtColor(array, cv2.COLOR_GRAY2BGR)
        if array.ndim != 3 or array.shape[2] != 3:
            raise ValueError("Expected a grayscale or BGR handwriting image.")
        return array.astype(np.uint8, copy=False)

    @staticmethod
    def _order_corners(corners: Sequence[Point]) -> np.ndarray:
        points = np.asarray(corners, dtype=np.float32).reshape(4, 2)
        if points.shape != (4, 2):
            raise ValueError("Exactly four page corners are required.")
        sums, diffs = points.sum(axis=1), np.diff(points, axis=1).ravel()
        return np.array([points[np.argmin(sums)], points[np.argmin(diffs)], points[np.argmax(sums)], points[np.argmax(diffs)]], dtype=np.float32)

    @classmethod
    def _detect_corners(cls, image: np.ndarray) -> Optional[np.ndarray]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 40, 140)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        h, w = gray.shape
        best = None
        best_area = 0.0
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < h * w * .18:
                continue
            perimeter = cv2.arcLength(contour, True)
            polygon = cv2.approxPolyDP(contour, .03 * perimeter, True)
            if len(polygon) == 4 and area > best_area:
                best, best_area = polygon[:, 0, :], area
        return cls._order_corners(best) if best is not None else None

    @staticmethod
    def _detail_score(gray: np.ndarray) -> float:
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        return float(np.var(laplacian))

    @staticmethod
    def _rotation(gray: np.ndarray) -> float:
        binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        points = np.column_stack(np.where(binary > 0))
        if len(points) < 20:
            return 0.0
        angle = cv2.minAreaRect(points.astype(np.float32))[-1]
        if angle < -45:
            angle += 90
        return float(angle)

    def process(self, image: np.ndarray, corners: Optional[Sequence[Point]] = None) -> Tuple[np.ndarray, PreservationReport]:
        source = self._validate(image)
        original_h, original_w = source.shape[:2]
        before_gray = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)
        warnings = []
        detected = self._order_corners(corners) if corners is not None else self._detect_corners(source)
        corrected = source
        perspective = detected is not None
        if detected is not None:
            tl, tr, br, bl = detected
            width = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
            height = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
            width, height = max(64, width), max(64, height)
            destination = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32)
            matrix = cv2.getPerspectiveTransform(detected, destination)
            corrected = cv2.warpPerspective(source, matrix, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        else:
            warnings.append("No page quadrilateral detected; perspective was not changed.")

        gray = cv2.cvtColor(corrected, cv2.COLOR_BGR2GRAY)
        angle = self._rotation(gray)
        if abs(angle) > 0.35 and abs(angle) < 15:
            h, w = corrected.shape[:2]
            matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
            corrected = cv2.warpAffine(corrected, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        elif abs(angle) >= 15:
            warnings.append("Rotation estimate was too large for automatic deskew; source orientation was retained.")
            angle = 0.0

        corrected_gray = cv2.cvtColor(corrected, cv2.COLOR_BGR2GRAY)
        # Divide by a blurred illumination field; CLAHE is limited to avoid halos
        # around strokes and keeps the corrected grayscale available to HTR.
        background = cv2.GaussianBlur(corrected_gray, (0, 0), 21)
        normalized = cv2.divide(corrected_gray, background, scale=180)
        normalized = cv2.createCLAHE(clipLimit=1.6, tileGridSize=(8, 8)).apply(normalized)
        result = cv2.cvtColor(normalized, cv2.COLOR_GRAY2BGR)
        if max(result.shape[:2]) > self.max_side:
            scale = self.max_side / max(result.shape[:2])
            result = cv2.resize(result, (round(result.shape[1] * scale), round(result.shape[0] * scale)), interpolation=cv2.INTER_AREA)
            warnings.append("Output was downscaled to the configured safe maximum side.")
        after_gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
        report = PreservationReport((original_w, original_h), (result.shape[1], result.shape[0]), perspective, angle, True, self._detail_score(before_gray), self._detail_score(after_gray), tuple(warnings))
        return result, report
