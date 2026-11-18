"""
Handwriting Sample Preprocessor
Production-grade OpenCV pipeline for glyph extraction from teacher sample sheets.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HandwritingPreprocessor:
    def __init__(self, min_contour_area: int = 80, max_contour_area: int = 15000, padding: int = 8):
        self.min_contour_area = min_contour_area
        self.max_contour_area = max_contour_area
        self.padding = padding

    def load_image(self, image_path: str | Path) -> np.ndarray:
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Sample image not found: {path}")
        img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise ValueError(f"Failed to load image: {path}")
        return img

    def deskew(self, image: np.ndarray) -> np.ndarray:
        coords = np.column_stack(np.where(image < 128))
        if len(coords) < 50:
            return image
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        if abs(angle) < 0.5:
            return image
        (h, w) = image.shape
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        return cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    def binarize(self, image: np.ndarray) -> np.ndarray:
        blurred = cv2.GaussianBlur(image, (3, 3), 0)
        return cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 21, 8)

    def remove_ruled_lines(self, binary: np.ndarray) -> np.ndarray:
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        detected_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=1)
        cleaned = cv2.subtract(binary, detected_lines)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        return cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel)

    def extract_glyphs(self, binary: np.ndarray, expected_order: Optional[List[str]] = None) -> List[Dict]:
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if self.min_contour_area < area < self.max_contour_area:
                x, y, w, h = cv2.boundingRect(cnt)
                aspect = w / float(h) if h > 0 else 0
                if 0.15 < aspect < 6.0 and h > 12:
                    candidates.append((x, y, w, h, area))
        candidates.sort(key=lambda c: (c[1] // 40, c[0]))
        glyphs = []
        for idx, (x, y, w, h, area) in enumerate(candidates):
            x1 = max(0, x - self.padding)
            y1 = max(0, y - self.padding)
            x2 = min(binary.shape[1], x + w + self.padding)
            y2 = min(binary.shape[0], y + h + self.padding)
            glyph_img = binary[y1:y2, x1:x2].copy()
            size = max(glyph_img.shape)
            canvas = np.zeros((size, size), dtype=np.uint8)
            oy = (size - glyph_img.shape[0]) // 2
            ox = (size - glyph_img.shape[1]) // 2
            canvas[oy:oy + glyph_img.shape[0], ox:ox + glyph_img.shape[1]] = glyph_img
            char_label = expected_order[idx] if expected_order and idx < len(expected_order) else f"glyph_{idx:03d}"
            glyphs.append({"index": idx, "label": char_label, "image": canvas, "bbox": (x, y, w, h), "area": area})
        return glyphs

    def process(self, image_path: str | Path, expected_chars: Optional[List[str]] = None, save_debug: bool = False, debug_dir: str = "debug_glyphs") -> List[Dict]:
        gray = self.load_image(image_path)
        deskewed = self.deskew(gray)
        binary = self.binarize(deskewed)
        cleaned = self.remove_ruled_lines(binary)
        glyphs = self.extract_glyphs(cleaned, expected_order=expected_chars)
        if save_debug:
            Path(debug_dir).mkdir(parents=True, exist_ok=True)
            for g in glyphs:
                cv2.imwrite(str(Path(debug_dir) / f"{g['label']}.png"), g["image"])
        return glyphs


DEFAULT_SAMPLE_ORDER = (
    list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") +
    list("abcdefghijklmnopqrstuvwxyz") +
    list("0123456789") +
    list("#=+-*()/{}[];:\"'")
)

if __name__ == "__main__":
    print("HandwritingPreprocessor ready.")
