"""Template-validated handwriting extraction. Ambiguous samples are rejected, never position-guessed."""
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
    """The uploaded sample cannot be mapped safely to the approved template."""


class HandwritingPreprocessor:
    def __init__(self, min_contour_area: int = 12, max_contour_area: int = 15000,
                 padding: int = 8, expected_rows: Sequence[str] = DEFAULT_SAMPLE_ROWS):
        self.min_contour_area = min_contour_area
        self.max_contour_area = max_contour_area
        self.padding = padding
        self.expected_rows = tuple(expected_rows)

    def load_image(self, image_path: str | Path) -> np.ndarray:
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Sample image not found: {path}")
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if image is None or image.size == 0 or min(image.shape) < 100:
            raise HandwritingSampleError("Image is unreadable or too small for the complete sample sheet.")
        return image

    def deskew(self, image: np.ndarray) -> np.ndarray:
        ink = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        coords = np.column_stack(np.where(ink > 0))
        if len(coords) < 100:
            raise HandwritingSampleError("Not enough handwriting was detected.")
        angle = cv2.minAreaRect(coords)[-1]
        angle = -(90 + angle) if angle < -45 else -angle
        if abs(angle) < 0.35:
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
        return cv2.morphologyEx(cv2.subtract(binary, lines), cv2.MORPH_OPEN,
                                cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)))

    @staticmethod
    def _row_bands(binary: np.ndarray, expected_count: int) -> List[Tuple[int, int]]:
        projection = np.count_nonzero(binary, axis=1)
        active = projection >= max(2, int(binary.shape[1] * 0.001))
        runs, start = [], None
        for y, value in enumerate(active):
            if value and start is None:
                start = y
            elif not value and start is not None:
                runs.append((start, y))
                start = None
        if start is not None:
            runs.append((start, len(active)))
        if not runs:
            raise HandwritingSampleError("No handwriting rows were detected.")
        typical = max(8, int(np.median([b-a for a, b in runs])))
        merged = []
        for top, bottom in runs:
            if merged and top - merged[-1][1] <= max(5, int(typical * 0.55)):
                merged[-1][1] = bottom
            else:
                merged.append([top, bottom])
        if len(merged) != expected_count:
            raise HandwritingSampleError(
                f"Expected {expected_count} separated template rows; detected {len(merged)}. "
                "Use the supplied six-row sample sheet and retake the photo."
            )
        return [(a, b) for a, b in merged]

    def _components_for_row(self, row: np.ndarray):
        # Reconnect short detached i/j dots vertically; never close horizontally.
        joined = cv2.morphologyEx(row, cv2.MORPH_CLOSE,
                                  cv2.getStructuringElement(cv2.MORPH_RECT, (1, 5)))
        count, _, stats, _ = cv2.connectedComponentsWithStats(joined, 8)
        items = []
        for i in range(1, count):
            x, y, w, h, area = map(int, stats[i])
            if self.min_contour_area <= area <= self.max_contour_area and h >= 5 and w >= 2:
                items.append((x, y, w, h, area))
        return sorted(items, key=lambda item: item[0])

    def extract_glyphs(self, binary: np.ndarray,
                       expected_order: Optional[Sequence[str]] = None) -> List[Dict]:
        expected = tuple("".join(self.expected_rows))
        if expected_order is not None and tuple(expected_order) != expected:
            raise HandwritingSampleError("Character order differs from the approved sample-sheet template.")
        bands = self._row_bands(binary, len(self.expected_rows))
        glyphs = []
        for row_no, ((top, bottom), row_chars) in enumerate(zip(bands, self.expected_rows), 1):
            row = binary[top:bottom, :]
            components = self._components_for_row(row)
            if len(components) != len(row_chars):
                raise HandwritingSampleError(
                    f"Row {row_no} requires {len(row_chars)} isolated samples "
                    f"({row_chars[0]}–{row_chars[-1]}), but {len(components)} were detected. "
                    "This row has not been mapped; correct the sample instead of guessing."
                )
            for col, (x, y, w, h, area) in enumerate(components):
                label = row_chars[col]
                x1, y1 = max(0, x-self.padding), max(0, y-self.padding)
                x2, y2 = min(row.shape[1], x+w+self.padding), min(row.shape[0], y+h+self.padding)
                crop = row[y1:y2, x1:x2].copy()
                if crop.size == 0 or np.count_nonzero(crop) < 8:
                    raise HandwritingSampleError(f"Sample {label!r} in row {row_no} is blank or too faint.")
                glyphs.append({"index": len(glyphs), "label": label, "image": crop,
                               "bbox": (x, top+y, w, h), "area": area,
                               "row": row_no, "column": col+1})
        if len(glyphs) != len(DEFAULT_SAMPLE_ORDER):
            raise HandwritingSampleError("The complete alphabet, digits and punctuation samples are required.")
        return glyphs

    def process(self, image_path: str | Path, expected_chars: Optional[List[str]] = None,
                save_debug: bool = False, debug_dir: str = "debug_glyphs") -> List[Dict]:
        cleaned = self.remove_ruled_lines(self.binarize(self.deskew(self.load_image(image_path))))
        glyphs = self.extract_glyphs(cleaned, expected_order=expected_chars)
        if save_debug:
            target = Path(debug_dir)
            target.mkdir(parents=True, exist_ok=True)
            for g in glyphs:
                cv2.imwrite(str(target / f"{g['index']:03d}_{ord(g['label']):04x}.png"), g["image"])
        return glyphs
