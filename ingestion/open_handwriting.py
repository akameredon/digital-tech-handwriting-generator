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
    perspective_corrected: bool
    deskew_degrees: float
    page_corners: Optional[List[List[int]]]

    def public_dict(self) -> Dict[str, Any]:
        return {
            "width": self.width, "height": self.height,
            "quality": self.quality, "warnings": self.warnings,
            "line_count": len(self.lines),
            "blur_score": round(self.blur_score, 2),
            "brightness": round(self.brightness, 2),
            "perspective_corrected": self.perspective_corrected,
            "deskew_degrees": round(self.deskew_degrees, 2),
            "page_corners": self.page_corners,
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
        if h * w > 24_000_000:
            raise HandwritingIntakeError("This image has too many pixels to process safely. Resize it to 24 megapixels or less.")
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

    @staticmethod
    def _order_corners(points: np.ndarray) -> np.ndarray:
        points = points.astype("float32")
        total = points.sum(axis=1)
        diff = np.diff(points, axis=1).reshape(-1)
        return np.array([
            points[np.argmin(total)], points[np.argmin(diff)],
            points[np.argmax(total)], points[np.argmax(diff)]
        ], dtype="float32")

    def _rectify_page(self, image: np.ndarray) -> Tuple[np.ndarray, bool, Optional[List[List[int]]]]:
        """Perspective-correct a confidently detected page quadrilateral."""
        height, width = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 40, 120)
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []
        for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:30]:
            perimeter = cv2.arcLength(contour, True)
            if perimeter <= 0:
                continue
            polygon = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
            area_ratio = cv2.contourArea(polygon) / float(width * height)
            if len(polygon) == 4 and cv2.isContourConvex(polygon) and 0.25 <= area_ratio <= 0.97:
                pts = polygon.reshape(4, 2)
                if np.min(pts[:, 0]) <= 2 or np.min(pts[:, 1]) <= 2:
                    continue
                if np.max(pts[:, 0]) >= width - 3 or np.max(pts[:, 1]) >= height - 3:
                    continue
                candidates.append((area_ratio, pts))
        if not candidates:
            return image, False, None
        _, raw = max(candidates, key=lambda item: item[0])
        corners = self._order_corners(raw)
        tl, tr, br, bl = corners
        out_w = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
        out_h = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
        if out_w < self.min_dimension or out_h < self.min_dimension:
            return image, False, None
        # Prevent perspective expansion from exceeding the decoded source budget.
        scale = min(1.0, 5000 / max(out_w, out_h))
        out_w, out_h = max(1, int(out_w * scale)), max(1, int(out_h * scale))
        target = np.array([[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]], dtype="float32")
        transform = cv2.getPerspectiveTransform(corners, target)
        warped = cv2.warpPerspective(image, transform, (out_w, out_h), flags=cv2.INTER_CUBIC,
                                     borderMode=cv2.BORDER_REPLICATE)
        return warped, True, [[int(x), int(y)] for x, y in corners]

    @staticmethod
    def _deskew(image: np.ndarray) -> Tuple[np.ndarray, float]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        min_length = max(80, int(image.shape[1] * 0.28))
        segments = cv2.HoughLinesP(edges, 1, np.pi / 1800, threshold=70,
                                   minLineLength=min_length, maxLineGap=max(12, int(image.shape[1] * 0.025)))
        if segments is None:
            return image, 0.0
        angles = []
        for x1, y1, x2, y2 in segments[:, 0]:
            angle = float(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            if abs(angle) <= 12:
                angles.append(angle)
        if len(angles) < 2:
            return image, 0.0
        correction = -float(np.median(angles))
        if abs(correction) < 0.5 or abs(correction) > 8:
            return image, 0.0
        h, w = image.shape[:2]
        matrix = cv2.getRotationMatrix2D((w / 2, h / 2), correction, 1.0)
        rotated = cv2.warpAffine(image, matrix, (w, h), flags=cv2.INTER_CUBIC,
                                 borderMode=cv2.BORDER_REPLICATE)
        return rotated, correction

    def analyze_bytes(self, image_bytes: bytes) -> PageAnalysis:
        image = self.decode(image_bytes)
        return self.analyze_image(image)

    def analyze(self, image_path: str | Path) -> PageAnalysis:
        return self.analyze_image(self.load(image_path))

    def analyze_image(self, image: np.ndarray) -> PageAnalysis:
        image, perspective_corrected, page_corners = self._rectify_page(image)
        image, deskew_degrees = self._deskew(image)
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
            column_ink = np.count_nonzero(region, axis=0)
            xs = np.where(column_ink > 0)[0]
            if len(xs) == 0:
                continue
            # A wide, sustained vertical gutter indicates independent columns;
            # ordinary word spaces are kept together as one reading line.
            active_columns = column_ink > 0
            gaps = []
            gap_start = None
            for x, active in enumerate(active_columns):
                if not active and gap_start is None:
                    gap_start = x
                elif active and gap_start is not None:
                    if x - gap_start >= max(45, int(width * 0.07)):
                        gaps.append((gap_start, x))
                    gap_start = None
            if gap_start is not None and width - gap_start >= max(45, int(width * 0.07)):
                gaps.append((gap_start, width))
            segments = []
            segment_start = int(xs[0])
            for gap_left, gap_right in gaps:
                if gap_left - segment_start >= int(width * 0.12):
                    segments.append((segment_start, gap_left))
                segment_start = gap_right
            if int(xs[-1]) + 1 - segment_start >= int(width * 0.12):
                segments.append((segment_start, int(xs[-1]) + 1))
            if not segments:
                segments = [(int(xs[0]), int(xs[-1]) + 1)]
            pad_y = max(4, int((bottom - top) * 0.12))
            y0, y1 = max(0, top - pad_y), min(height, bottom + pad_y)
            for segment_left, segment_right in segments:
                local_xs = np.where(column_ink[segment_left:segment_right] > 0)[0]
                if len(local_xs) == 0:
                    continue
                left = max(0, segment_left + int(local_xs[0]) - 8)
                right = min(width, segment_left + int(local_xs[-1]) + 9)
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
        return PageAnalysis(width, height, quality, warnings, lines, blur_score, brightness,\n                            perspective_corrected, deskew_degrees, page_corners)


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
