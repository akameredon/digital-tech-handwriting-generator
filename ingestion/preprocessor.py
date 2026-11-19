"""Open handwriting extraction for real teacher photos.

Accepts ordinary classroom handwriting sheets. Does not require an exact
six-row template. Filters for letter-like shapes (rejects ruled-line scraps
and spiral-binding holes) so the compiled font stays readable.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
import cv2
import numpy as np

DEFAULT_SAMPLE_ROWS: Tuple[str, ...] = (
    "ABCDEFGHIJKLM", "NOPQRSTUVWXYZ",
    "abcdefghijklm", "nopqrstuvwxyz",
    "0123456789", ".,;:!?'\"()-+=/*",
)
DEFAULT_SAMPLE_ORDER = [c for row in DEFAULT_SAMPLE_ROWS for c in row]


class HandwritingSampleError(ValueError):
    """The uploaded sample cannot be used at all."""


class HandwritingPreprocessor:
    def __init__(
        self,
        min_contour_area: int = 60,
        max_contour_area: int = 4000,
        padding: int = 4,
        expected_rows: Sequence[str] = DEFAULT_SAMPLE_ROWS,
    ):
        self.min_contour_area = min_contour_area
        self.max_contour_area = max_contour_area
        self.padding = padding
        self.expected_rows = tuple(expected_rows)

    def load_image(self, image_path: str | Path) -> np.ndarray:
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Sample image not found: {path}")
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if image is None or image.size == 0 or min(image.shape) < 40:
            raise HandwritingSampleError("Image is unreadable or too small. Take a clearer photo.")
        h, w = image.shape[:2]
        if w > 200:
            image = image[:, int(w * 0.08):]
        h, w = image.shape[:2]
        if max(h, w) > 1800:
            scale = 1800.0 / max(h, w)
            image = cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        return image

    def deskew(self, image: np.ndarray) -> np.ndarray:
        ink = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        coords = np.column_stack(np.where(ink > 0))
        if len(coords) < 40:
            return image
        angle = cv2.minAreaRect(coords)[-1]
        angle = -(90 + angle) if angle < -45 else -angle
        if abs(angle) < 0.5:
            return image
        h, w = image.shape
        matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        return cv2.warpAffine(
            image, matrix, (w, h), flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT, borderValue=255,
        )

    def binarize(self, image: np.ndarray) -> np.ndarray:
        return cv2.adaptiveThreshold(
            cv2.medianBlur(image, 3), 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 11,
        )

    def remove_ruled_lines(self, binary: np.ndarray) -> np.ndarray:
        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (max(40, binary.shape[1] // 12), 1)
        )
        lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
        cleaned = cv2.subtract(binary, lines)
        return cv2.morphologyEx(
            cleaned, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (2, 3))
        )

    def _is_letterlike(self, w: int, h: int, area: int, roi: np.ndarray) -> bool:
        if area < self.min_contour_area or area > self.max_contour_area:
            return False
        if h < 14 or w < 4:
            return False
        aspect = w / max(1, h)
        if aspect > 1.8 or aspect < 0.12:
            return False
        if 0.7 <= aspect <= 1.35 and area > 200:
            fill = float(np.count_nonzero(roi)) / max(1, w * h)
            peri = 2 * (w + h)
            circ = 4.0 * np.pi * area / max(1.0, peri * peri)
            if fill > 0.55 and circ > 0.5:
                return False
        return True

    def _components(self, binary: np.ndarray):
        joined = cv2.morphologyEx(
            binary, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (2, 6))
        )
        count, _, stats, _ = cv2.connectedComponentsWithStats(joined, 8)
        items = []
        for i in range(1, count):
            x, y, w, h, area = map(int, stats[i])
            roi = binary[y : y + h, x : x + w]
            if self._is_letterlike(w, h, area, roi):
                items.append((x, y, w, h, area))
        if not items:
            return []
        median_h = max(10.0, float(np.median([item[3] for item in items])))
        col_bin = max(40, int(median_h * 1.6))
        items.sort(key=lambda item: (item[0] // col_bin, item[1], item[0]))
        return items

    def extract_glyphs(
        self, binary: np.ndarray, expected_order: Optional[Sequence[str]] = None
    ) -> List[Dict]:
        labels = list(expected_order) if expected_order is not None else list(DEFAULT_SAMPLE_ORDER)
        components = self._components(binary)
        if not components:
            h = binary.shape[0]
            for frac in (0.50, 0.65, 0.80):
                components = self._components(binary[: max(40, int(h * frac)), :])
                if len(components) >= 8:
                    break
        if not components:
            raise HandwritingSampleError(
                "No clear letter shapes were found. Write separate letters with space between them on light paper."
            )

        glyphs: List[Dict] = []
        seen = set()
        for x, y, w, h, area in components:
            if len(glyphs) >= max(len(labels), 70):
                break
            label = labels[len(glyphs)] if len(glyphs) < len(labels) else None
            if label is None or label in seen:
                continue
            x1, y1 = max(0, x - self.padding), max(0, y - self.padding)
            x2 = min(binary.shape[1], x + w + self.padding)
            y2 = min(binary.shape[0], y + h + self.padding)
            crop = binary[y1:y2, x1:x2].copy()
            if crop.size == 0 or np.count_nonzero(crop) < 8:
                continue
            seen.add(label)
            glyphs.append(
                {
                    "index": len(glyphs),
                    "label": label,
                    "image": crop,
                    "bbox": (x, y, w, h),
                    "area": area,
                    "row": 1,
                    "column": len(glyphs) + 1,
                }
            )
        if len(glyphs) < 8:
            raise HandwritingSampleError(
                "Too few clear letters were detected. Write letters more clearly with space between them."
            )
        return glyphs

    def process(
        self,
        image_path: str | Path,
        expected_chars: Optional[List[str]] = None,
        save_debug: bool = False,
        debug_dir: str = "debug_glyphs",
    ) -> List[Dict]:
        gray = self.load_image(image_path)
        cleaned = self.remove_ruled_lines(self.binarize(self.deskew(gray)))
        glyphs = self.extract_glyphs(cleaned, expected_order=expected_chars)
        if save_debug:
            target = Path(debug_dir)
            target.mkdir(parents=True, exist_ok=True)
            for g in glyphs:
                safe = str(g["label"]).replace("/", "slash")
                cv2.imwrite(str(target / f"{g['index']:03d}_{safe}.png"), g["image"])
        return glyphs
