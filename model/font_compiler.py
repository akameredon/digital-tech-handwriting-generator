"""
Font Compiler
Takes extracted glyphs from the preprocessor and builds a basic TrueType font.
Production path uses fontTools.
"""

from pathlib import Path
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

try:
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    FONTTOOLS_AVAILABLE = True
except ImportError:
    FONTTOOLS_AVAILABLE = False
    logger.warning("fontTools not available – font compilation will be limited")


class FontCompiler:
    """
    Compiles a set of glyph images into a basic .ttf font.
    """

    def __init__(self, units_per_em: int = 1000, ascender: int = 800, descender: int = -200):
        self.units_per_em = units_per_em
        self.ascender = ascender
        self.descender = descender

    def _image_to_glyph_pen(self, image, glyph_name: str):
        if not FONTTOOLS_AVAILABLE:
            return None
        pen = TTGlyphPen(None)
        # Placeholder outline – real production should vectorize the glyph image
        pen.moveTo((50, 50))
        pen.lineTo((50, 700))
        pen.lineTo((500, 700))
        pen.lineTo((500, 50))
        pen.closePath()
        return pen.glyph()

    def compile(
        self,
        glyphs: List[Dict],
        output_path: str | Path,
        family_name: str = "TeacherHandwriting",
        style_name: str = "Regular"
    ) -> Optional[Path]:
        if not FONTTOOLS_AVAILABLE:
            logger.error("fontTools is required for font compilation")
            return None

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        fb = FontBuilder(self.units_per_em, isTTF=True)
        fb.setupGlyphOrder([".notdef"] + [g["label"] for g in glyphs])
        fb.setupCharacterMap({ord(g["label"]): g["label"] for g in glyphs if len(g["label"]) == 1})

        glyphs_dict = {".notdef": self._image_to_glyph_pen(None, ".notdef")}
        for g in glyphs:
            glyphs_dict[g["label"]] = self._image_to_glyph_pen(g.get("image"), g["label"])

        fb.setupGlyf(glyphs_dict)
        fb.setupHorizontalMetrics({name: (600, 50) for name in glyphs_dict})
        fb.setupHorizontalHeader(ascent=self.ascender, descent=self.descender)
        fb.setupNameTable({
            "familyName": family_name,
            "styleName": style_name,
            "uniqueFontName": f"{family_name}-{style_name}",
            "fullName": f"{family_name} {style_name}",
            "version": "1.0",
            "psName": f"{family_name}-{style_name}".replace(" ", "")
        })
        fb.setupOS2()
        fb.setupPost()

        fb.save(str(output_path))
        logger.info(f"Font written to {output_path}")
        return output_path


if __name__ == "__main__":
    print("FontCompiler module loaded. fontTools available:", FONTTOOLS_AVAILABLE)
