"""
Font Compiler – Production version
Takes extracted glyphs from the preprocessor and builds a usable TrueType font
by converting binary glyph images into vector outlines via contour approximation.
"""

from pathlib import Path
from typing import List, Dict, Optional, Tuple
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
    logger.warning("fontTools not available")


class FontCompiler:
    def __init__(self, units_per_em: int = 1000, ascender: int = 800, descender: int = -200, target_height: int = 700):
        self.units_per_em = units_per_em
        self.ascender = ascender
        self.descender = descender
        self.target_height = target_height

    def _normalize_and_scale(self, image: np.ndarray) -> Tuple[np.ndarray, float]:
        if image is None or image.size == 0:
            return image, 1.0
        if image.max() > 1:
            _, binary = cv2.threshold(image, 127, 255, cv2.THRESH_BINARY)
        else:
            binary = (image * 255).astype(np.uint8)
        ys, xs = np.where(binary > 0)
        if len(xs) == 0:
            return binary, 1.0
        min_y, max_y = ys.min(), ys.max()
        h = max(1, max_y - min_y)
        scale = self.target_height / h
        return binary, scale

    def _image_to_glyph(self, image: Optional[np.ndarray], glyph_name: str):
        if not FONTTOOLS_AVAILABLE:
            return None
        pen = TTGlyphPen(None)
        if image is None or not OPENCV_AVAILABLE:
            pen.moveTo((50, 50))
            pen.lineTo((50, 700))
            pen.lineTo((400, 700))
            pen.lineTo((400, 50))
            pen.closePath()
            return pen.glyph()

        binary, scale = self._normalize_and_scale(image)
        contours, _ = cv2.findContours(binary, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            pen.moveTo((0, 0))
            pen.lineTo((0, 1))
            pen.closePath()
            return pen.glyph()

        for cnt in contours:
            epsilon = 0.005 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, epsilon, True)
            if len(approx) < 3:
                continue
            points = []
            for pt in approx:
                x, y = pt[0]
                fx = int(x * scale)
                fy = int((binary.shape[0] - y) * scale)
                points.append((fx, fy))
            pen.moveTo(points[0])
            for p in points[1:]:
                pen.lineTo(p)
            pen.closePath()
        return pen.glyph()

    def compile(self, glyphs: List[Dict], output_path: str | Path, family_name: str = "TeacherHandwriting", style_name: str = "Regular") -> Optional[Path]:
        if not FONTTOOLS_AVAILABLE:
            logger.error("fontTools is required")
            return None
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        valid_glyphs = []
        for g in glyphs:
            label = str(g.get("label", "")).strip()
            if len(label) == 1:
                valid_glyphs.append({**g, "label": label})
        if not valid_glyphs:
            valid_glyphs = [{"label": "A", "image": None}]

        glyph_order = [".notdef"] + [g["label"] for g in valid_glyphs]
        cmap = {ord(g["label"]): g["label"] for g in valid_glyphs}

        fb = FontBuilder(self.units_per_em, isTTF=True)
        fb.setupGlyphOrder(glyph_order)
        fb.setupCharacterMap(cmap)

        glyphs_dict = {".notdef": self._image_to_glyph(None, ".notdef")}
        metrics = {".notdef": (600, 50)}
        for g in valid_glyphs:
            glyphs_dict[g["label"]] = self._image_to_glyph(g.get("image"), g["label"])
            metrics[g["label"]] = (600, 40)

        fb.setupGlyf(glyphs_dict)
        fb.setupHorizontalMetrics(metrics)
        fb.setupHorizontalHeader(ascent=self.ascender, descent=self.descender)
        fb.setupNameTable({
            "familyName": family_name,
            "styleName": style_name,
            "uniqueFontName": f"{family_name}-{style_name}",
            "fullName": f"{family_name} {style_name}",
            "version": "1.0",
            "psName": f"{family_name}-{style_name}".replace(" ", ""),
        })
        fb.setupOS2()
        fb.setupPost()
        fb.save(str(output_path))
        logger.info(f"Font written to {output_path}")
        return output_path


if __name__ == "__main__":
    print("FontCompiler ready. OpenCV:", OPENCV_AVAILABLE, "fontTools:", FONTTOOLS_AVAILABLE)
