"""Natural-page handwriting intake; never assigns character labels by position."""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError


MAX_NATURAL_PAGE_BYTES = 12 * 1024 * 1024
SUPPORTED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


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
    blur_score: float
    brightness: float

    def public_dict(self) -> Dict[str, Any]:
        return {
            "width": self.width, "height": self.height,
            "quality": self.quality, "warnings": self.warnings,
            "line_count": len(self.lines),
            "blur_score": round(self.blur_score, 2),
            "brightness": round(self.brightness, 2),
            "lines": [
                {"index": line.index, "bbox": list(line.bbox),
                 "ink_ratio": round(line.ink_ratio, 4)}
                for line in self.lines
            ],
        }


class HandwritingRecognizer(Protocol):
    """Adapter contract for a genuine handwritten-text recognition model."""
    name: str

    def recognize_lines(self, lines: Sequence[np.ndarray]) -> List[Dict[str, Any]]:
        """Return one {text, confidence} result per line crop."""


class RecognitionUnavailable(RuntimeError):
    pass


class OpenHandwritingIntake:
    """Analyze ordinary handwritten pages without fixed rows or character order."""

    def __init__(self, min_dimension: int = 180, min_ink_pixels: int = 80,
                 max_bytes: int = MAX_NATURAL_PAGE_BYTES):
        self.min_dimension = min_dimension
        self.min_ink_pixels = min_ink_pixels
        self.max_bytes = max_bytes

    def decode(self, image_bytes: bytes) -> np.ndarray:
        if not image_bytes:
            raise HandwritingIntakeError("The uploaded image is empty. Choose a JPG, PNG or WebP photo.")
        if len(image_bytes) > self.max_bytes:
            raise HandwritingIntakeError("The image is larger than the 12 MB upload limit.")
        try:
            with Image.open(BytesIO(image_bytes)) as source:
                if source.format not in SUPPORTED_IMAGE_FORMATS:
                    raise HandwritingIntakeError("Unsupported image format. Upload a JPG, PNG or WebP photo.")
                source.load()
                oriented = ImageOps.exif_transpose(source).convert("RGB")
                image = cv2.cvtColor(np.asarray(oriented), cv2.COLOR_RGB2BGR)
        except HandwritingIntakeError:
            raise
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise HandwritingIntakeError("We could not read this image. Choose a valid JPG, PNG or WebP photo.") from exc
        h, w = image.shape[:2]
        if min(h, w) < self.min_dimension:
            raise HandwritingIntakeError("This image is too small. Upload a higher-resolution photo of your handwriting.")
        return image

    def load(self, image_path: str | Path) -> np.ndarray:
        try:
            data = Path(image_path).read_bytes()
        except OSError as exc:
            raise HandwritingIntakeError("We could not read this image. Choose a clear JPG, PNG or WebP photo.") from exc
        return self.decode(data)

    @staticmethod
    def _remove_page_rules(binary: np.ndarray) -> np.ndarray:
        horizontal = cv2.getStructuringElement(
            cv2.MORPH_RECT, (max(35, binary.shape[1] // 16), 1)
        )
        rules = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal, iterations=1)
        return cv2.subtract(binary, rules)

    def analyze_bytes(self, image_bytes: bytes) -> PageAnalysis:
        image = self.decode(image_bytes)
        return self.analyze_image(image)

    def analyze(self, image_path: str | Path) -> PageAnalysis:
        return self.analyze_image(self.load(image_path))

    def analyze_image(self, image: np.ndarray) -> PageAnalysis:
        height, width = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        brightness = float(np.mean(gray))
        enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        binary = cv2.threshold(
            enhanced, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )[1]
        binary = self._remove_page_rules(binary)
        binary = cv2.morphologyEx(
            binary, cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)), iterations=1
        )
        if int(cv2.countNonZero(binary)) < self.min_ink_pixels:
            raise HandwritingIntakeError(
                "We could not find enough visible handwriting. Try a closer, clearer photo."
            )

        # Projection segmentation adapts to the number and spacing of natural lines.
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
            lines.append(TextLineRegion(
                len(lines), (left, y0, right - left, y1 - y0), crop, line_ink / area
            ))

        if not lines:
            raise HandwritingIntakeError("We could not detect handwriting lines in this image.")
        warnings: List[str] = []
        if len(lines) < 2:
            warnings.append("Only one text line was detected; more handwriting may improve style coverage.")
        if width > height * 1.8:
            warnings.append("This is a wide image. Check that the full page is visible.")
        if blur_score < 45:
            warnings.append("The photo appears soft or out of focus. Retake it with the writing sharply focused.")
        if brightness < 55:
            warnings.append("The photo is very dark. Improve the lighting and retake the page.")
        elif brightness > 225:
            warnings.append("The page is overexposed. Reduce glare and retake the photo.")
        quality = "usable" if len(lines) >= 2 and blur_score >= 45 and 55 <= brightness <= 225 else "limited"
        return PageAnalysis(width, height, quality, warnings, lines, blur_score, brightness)


class ConfiguredRecognizer:
    """Use an explicitly injected model; never fabricate recognized text."""
    def __init__(self, provider: Optional[HandwritingRecognizer] = None):
        self.provider = provider

    @property
    def available(self) -> bool:
        return self.provider is not None

    def recognize(self, analysis: PageAnalysis) -> List[Dict[str, Any]]:
        if self.provider is None:
            raise RecognitionUnavailable(
                "Handwriting recognition is not configured on this server yet. "
                "Your image was accepted, but text recognition and font generation are not available."
            )
        results = self.provider.recognize_lines([line.crop for line in analysis.lines])
        if len(results) != len(analysis.lines):
            raise RuntimeError("The handwriting recognizer returned an unexpected number of line results.")
        normalized = []
        for line, result in zip(analysis.lines, results):
            text = str(result.get("text", ""))
            confidence = float(result.get("confidence", 0.0))
            normalized.append({
                "line_index": line.index, "bbox": list(line.bbox),
                "text": text, "confidence": max(0.0, min(1.0, confidence)),
                "needs_review": confidence < 0.85,
            })
        return normalized
