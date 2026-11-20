"""Open handwriting extraction for real teacher photos (no exact template required)."""
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
    def __init__(self, min_contour_area: int = 20, max_contour_area: int = 25000,
                 padding: int = 6, expected_rows: Sequence[str] = DEFAULT_SAMPLE_ROWS):
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
        if max(h, w) > 2000:
            scale = 2000.0 / max(h, w)
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
        return cv2.warpAffine(image, matrix, (w, h), flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=255)

    def binarize(self, image: np.ndarray) -> np.ndarray:
        return cv2.adaptiveThreshold(cv2.medianBlur(image, 3), 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 12)

    def remove_ruled_lines(self, binary: np.ndarray) -> np.ndarray:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(30, binary.shape[1] // 18), 1))
        lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
        cleaned = cv2.subtract(binary, lines)
        return cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)))

    def _components(self, binary: np.ndarray):
        joined = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 5)))
        count, _, stats, _ = cv2.connectedComponentsWithStats(joined, 8)
        items = []
        for i in range(1, count):
            x, y, w, h, area = map(int, stats[i])
            if self.min_contour_area <= area <= self.max_contour_area and h >= 3 and w >= 1:
                items.append((x, y, w, h, area))
        if not items:
            return []
        median_h = max(6.0, float(np.median([item[3] for item in items])))
        items.sort(key=lambda item: (item[1] // max(12, int(median_h * 0.9)), item[0]))
        return items

    def extract_glyphs(self, binary: np.ndarray, expected_order: Optional[Sequence[str]] = None) -> List[Dict]:
        # expected_order is retained for call compatibility only. Position is
        # never evidence of Unicode identity; this extractor returns unlabeled
        # image regions for later recognition/review.
        components = self._components(binary)
        if not components:
            h = binary.shape[0]
            for frac in (0.45, 0.55, 0.65, 0.75):
                components = self._components(binary[: max(40, int(h * frac)), :])
                if components:
                    break
        if not components:
            raise HandwritingSampleError(
                "No handwriting characters were found. Use a clearer photo with dark ink on light paper."
            )
        if len(components) > len(labels) * 1.6:
            h = binary.shape[0]
            best = components
            for frac in (0.40, 0.50, 0.55, 0.60, 0.70):
                band = self._components(binary[: max(40, int(h * frac)), :])
                if band and abs(len(band) - len(labels)) < abs(len(best) - len(labels)):
                    best = band
            components = best
        glyphs = []
        for x, y, w, h, area in components:
            if len(glyphs) >= 300:
                break
            x1, y1 = max(0, x - self.padding), max(0, y - self.padding)
            x2, y2 = min(binary.shape[1], x + w + self.padding), min(binary.shape[0], y + h + self.padding)
            crop = binary[y1:y2, x1:x2].copy()
            if crop.size == 0 or np.count_nonzero(crop) < 6:
                continue
            glyphs.append({"index": len(glyphs), "label": None, "image": crop,
                           "bbox": (x, y, w, h), "area": area, "row": 1, "column": len(glyphs) + 1,
                           "confirmed": False, "provenance": "unlabeled_component"})
        if len(glyphs) < 8:
            raise HandwritingSampleError(
                "Too few clear characters were detected. Write letters more clearly and try again."
            )
        return glyphs

    def process(self, image_path: str | Path, expected_chars: Optional[List[str]] = None,
                save_debug: bool = False, debug_dir: str = "debug_glyphs") -> List[Dict]:
        gray = self.load_image(image_path)
        cleaned = self.remove_ruled_lines(self.binarize(self.deskew(gray)))
        glyphs = self.extract_glyphs(cleaned, expected_order=expected_chars)
        if save_debug:
            target = Path(debug_dir)
            target.mkdir(parents=True, exist_ok=True)
            for g in glyphs:
                x, y, w, h = g["bbox"]
                cv2.imwrite(str(target / f"{g['index']:03d}_x{x}_y{y}_w{w}_h{h}.png"), g["image"])
        return glyphs
