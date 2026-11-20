"""Compile only teacher-confirmed handwriting glyphs into a partial TrueType font."""
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

PREFERRED_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:!?'\\"()-+=/*"


class FontCompilationError(ValueError):
    """The supplied confirmed glyph set cannot produce a usable font."""


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

    def _notdef_glyph(self):
        # .notdef is a font-format fallback, never mapped to a teacher character.
        pen = TTGlyphPen(None)
        pen.moveTo((50, 50))
        pen.lineTo((50, 700))
        pen.lineTo((450, 700))
        pen.lineTo((450, 50))
        pen.closePath()
        return pen.glyph()

    def _image_to_glyph(self, image, glyph_name: str, row: int,
                        metrics_out: Dict[str, Tuple[int, int]]):
        if not OPENCV_AVAILABLE or not FONTTOOLS_AVAILABLE:
            raise FontCompilationError("OpenCV and fontTools are required to compile handwriting.")
        if image is None or image.size == 0 or image.ndim != 2:
            raise FontCompilationError(f"Glyph {glyph_name} has no valid grayscale image.")
        binary = (image > 0).astype(np.uint8) * 255
        ys, xs = np.where(binary > 0)
        if len(xs) < 6:
            raise FontCompilationError(f"Glyph {glyph_name} is empty or too faint.")
        x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
        crop = binary[y0:y1 + 1, x0:x1 + 1]
        crop = cv2.copyMakeBorder(crop, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=0)
        height, width = crop.shape
        target = int(self.target_height * 0.72) if row in (3, 4) else self.target_height
        scale = target / max(1, height)
        glyph_width = max(1, int(round(width * scale)))
        side_bearing = max(40, int(round(target * 0.08)))
        advance = glyph_width + side_bearing * 2
        pen = TTGlyphPen(None)
        contours, hierarchy = cv2.findContours(crop, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            raise FontCompilationError(f"Glyph {glyph_name} contains no drawable contours.")
        drew = False
        for index, contour in enumerate(contours):
            if len(contour) < 3:
                continue
            epsilon = 0.002 * cv2.arcLength(contour, True)
            contour = cv2.approxPolyDP(contour, max(0.5, epsilon), True)
            if len(contour) < 3:
                continue
            points = []
            for point in contour[:, 0, :]:
                px = side_bearing + int(round(float(point[0]) * scale))
                py = int(round((height - 1 - point[1]) * scale))
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
            raise FontCompilationError(f"Glyph {glyph_name} has no usable contour.")
        metrics_out[glyph_name] = (advance, side_bearing)
        return pen.glyph()

    def compile(self, glyphs: List[Dict], output_path: str | Path,
                family_name: str = "TeacherHandwriting", style_name: str = "Regular") -> Optional[Path]:
        if not FONTTOOLS_AVAILABLE or not OPENCV_AVAILABLE:
            raise FontCompilationError("fontTools and OpenCV are required.")
        if not glyphs:
            raise FontCompilationError("No confirmed handwriting samples were supplied.")

        by_label: Dict[str, Dict] = {}
        for glyph in glyphs:
            label = str(glyph.get("label", ""))
            if len(label) != 1 or not glyph.get("confirmed", False):
                continue
            if glyph.get("provenance") not in {"teacher_corrected", "teacher_drawn"}:
                rejected += 1
                continue
            image = glyph.get("image")
            if image is None or not isinstance(image, np.ndarray) or image.size == 0:
                rejected += 1
                continue
            by_label.setdefault(label, glyph)

        if len(by_label) < 8:
            raise FontCompilationError(
                f"Only {len(by_label)} confirmed usable characters were supplied; at least 8 are required."
            )

        chars = [char for char in PREFERRED_CHARS if char in by_label]
        chars.extend(sorted(char for char in by_label if char not in PREFERRED_CHARS))
        glyf = {".notdef": self._notdef_glyph()}
        metrics = {".notdef": (550, 50)}
        compiled_chars: List[str] = []
        for char in chars:
            name = self._glyph_name(char)
            item = by_label[char]
            row = int(item.get("row", 1))
            try:
                glyf[name] = self._image_to_glyph(item["image"], name, row, metrics)
                compiled_chars.append(char)
            except FontCompilationError as exc:
                logger.warning("Skipping unusable confirmed glyph %r: %s", char, exc)
        if len(compiled_chars) < 8:
            raise FontCompilationError("Fewer than 8 confirmed glyphs had usable outlines.")

        # Both glyph order and cmap contain only teacher-provided outlines
        # that successfully compiled; missing or rejected characters stay absent.
        glyph_order = [".notdef"] + [self._glyph_name(char) for char in compiled_chars]
        cmap = {ord(char): self._glyph_name(char) for char in compiled_chars}
        builder = FontBuilder(self.units_per_em, isTTF=True)
        builder.setupGlyphOrder(glyph_order)
        builder.setupCharacterMap(cmap)
        builder.setupGlyf(glyf)
        builder.setupHorizontalMetrics(metrics)
        builder.setupHorizontalHeader(ascent=self.ascender, descent=self.descender)
        builder.setupNameTable({
            "familyName": family_name,
            "styleName": style_name,
            "uniqueFontIdentifier": f"{family_name}-{style_name}",
            "fullName": f"{family_name} {style_name}",
            "version": "1.2.0",
            "psName": f"{family_name}-{style_name}".replace(" ", ""),
        })
        builder.setupOS2()
        builder.setupPost()
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        builder.save(str(output))
        return output
