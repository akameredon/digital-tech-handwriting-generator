"""Build a TrueType font from teacher handwriting glyphs."""
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
import numpy as np

logger = logging.getLogger(__name__)
try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
try:
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    FONTTOOLS_AVAILABLE = True
except ImportError:
    FONTTOOLS_AVAILABLE = False

PREFERRED_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:!?'\"()-+=/*"


class FontCompilationError(ValueError):
    """The supplied glyph set cannot produce a usable font."""


class FontCompiler:
    def __init__(self, units_per_em: int = 1000, ascender: int = 800,
                 descender: int = -200, target_height: int = 700):
        self.units_per_em = units_per_em
        self.ascender = ascender
        self.descender = descender
        self.target_height = target_height

    @staticmethod
    def _glyph_name(char: str) -> str:
        return f"uni{ord(char):04X}"

    def _simple_box_glyph(self):
        pen = TTGlyphPen(None)
        pen.moveTo((50, 50))
        pen.lineTo((50, 700))
        pen.lineTo((450, 700))
        pen.lineTo((450, 50))
        pen.closePath()
        return pen.glyph()

    def _image_to_glyph(self, image, glyph_name: str, row: int, metrics_out: Dict[str, Tuple[int, int]]):
        if not OPENCV_AVAILABLE or not FONTTOOLS_AVAILABLE:
            raise FontCompilationError("OpenCV and fontTools are required to compile handwriting.")
        if image is None or image.size == 0 or image.ndim != 2:
            raise FontCompilationError(f"Glyph {glyph_name} has no valid image.")
        binary = (image > 0).astype(np.uint8) * 255
        ys, xs = np.where(binary > 0)
        if len(xs) < 6:
            raise FontCompilationError(f"Glyph {glyph_name} is empty or too faint.")
        x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
        crop = binary[y0:y1 + 1, x0:x1 + 1]
        crop = cv2.copyMakeBorder(crop, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=0)
        h, w = crop.shape
        target = int(self.target_height * 0.72) if row in (3, 4) else self.target_height
        scale = target / max(1, h)
        glyph_w = max(1, int(round(w * scale)))
        side_bearing = max(40, int(round(target * 0.08)))
        advance = glyph_w + side_bearing * 2
        x_offset = side_bearing
        pen = TTGlyphPen(None)
        contours, hierarchy = cv2.findContours(crop, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            raise FontCompilationError(f"Glyph {glyph_name} contains no drawable contours.")
        drew = False
        for index, contour in enumerate(contours):
            if len(contour) < 3:
                continue
            eps = 0.002 * cv2.arcLength(contour, True)
            contour = cv2.approxPolyDP(contour, max(0.5, eps), True)
            if len(contour) < 3:
                continue
            points = []
            for point in contour[:, 0, :]:
                px = x_offset + int(round(float(point[0]) * scale))
                py = int(round(float(h - 1 - point[1]) * scale))
                points.append((px, py))
            is_hole = hierarchy is not None and hierarchy[0][index][3] >= 0
            if is_hole:
                points.reverse()
            pen.moveTo(points[0])
            for point in points[1:]:
                pen.lineTo(point)
            pen.closePath()
            drew = True
        if not drew:
            raise FontCompilationError(f"Glyph {glyph_name} had no usable contour.")
        metrics_out[glyph_name] = (advance, side_bearing)
        return pen.glyph()

    def compile(self, glyphs: List[Dict], output_path: str | Path,
                family_name: str = "TeacherHandwriting", style_name: str = "Regular") -> Optional[Path]:
        if not FONTTOOLS_AVAILABLE or not OPENCV_AVAILABLE:
            raise FontCompilationError("fontTools and OpenCV are required.")
        if not glyphs:
            raise FontCompilationError("No handwriting samples were supplied.")

        by_label: Dict[str, Dict] = {}
        for glyph in glyphs:
            label = str(glyph.get("label", ""))
            if len(label) != 1:
                continue
            if label not in by_label:
                by_label[label] = glyph

        if len(by_label) < 8:
            raise FontCompilationError(
                f"Only {len(by_label)} usable characters found. Write more letters clearly and try again."
            )

        chars = [c for c in PREFERRED_CHARS if c in by_label]
        for c in PREFERRED_CHARS:
            if c not in by_label:
                chars.append(c)

        glyph_order = [".notdef"] + [self._glyph_name(c) for c in chars]
        cmap = {ord(c): self._glyph_name(c) for c in chars}
        fb = FontBuilder(self.units_per_em, isTTF=True)
        fb.setupGlyphOrder(glyph_order)
        fb.setupCharacterMap(cmap)

        glyf = {".notdef": self._simple_box_glyph()}
        metrics = {".notdef": (550, 50)}
        for char in chars:
            name = self._glyph_name(char)
            if char in by_label:
                try:
                    row = int(by_label[char].get("row", 1))
                    glyf[name] = self._image_to_glyph(by_label[char].get("image"), name, row, metrics)
                    continue
                except FontCompilationError:
                    logger.warning("Skipping faint glyph %r", char)
            glyf[name] = self._simple_box_glyph()
            metrics[name] = (550, 50)

        fb.setupGlyf(glyf)
        fb.setupHorizontalMetrics(metrics)
        fb.setupHorizontalHeader(ascent=self.ascender, descent=self.descender)
        fb.setupNameTable({
            "familyName": family_name, "styleName": style_name,
            "uniqueFontIdentifier": f"{family_name}-{style_name}",
            "fullName": f"{family_name} {style_name}",
            "version": "1.1.2", "psName": f"{family_name}-{style_name}".replace(" ", ""),
        })
        fb.setupOS2()
        fb.setupPost()
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fb.save(str(output_path))
        return output_path
