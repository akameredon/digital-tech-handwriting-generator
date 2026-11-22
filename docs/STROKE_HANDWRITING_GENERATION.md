# Authentic unseen-handwriting generation

The repository now includes `renderer/stroke_handwriting.py`, a trajectory renderer for Rank 1 of the handwriting roadmap. It generates new words and lesson text from pen movements rather than substituting an installed font or repeating raster glyphs.

## What is implemented

- Reusable per-character pen trajectories for letters, digits, and punctuation.
- Separate capital gestures and lowercase gestures.
- Cursive-style ligature paths between adjacent glyphs.
- Writer-level slant, scale, stroke width, spacing, ink color, and connection settings.
- Per-realization baseline drift, glyph-size drift, slant drift, pressure-like width variation, and seeded randomness.
- Ruled notebook rendering and multi-line lesson text.
- JSON writer profiles with overrideable trajectories, ready for verified teacher-sample extraction.

## Usage

```python
from renderer.stroke_handwriting import HandwritingRenderer, WriterProfile

profile = WriterProfile.load("teacher.json")
image = HandwritingRenderer(profile, seed=2025).render(
    "Lesson 4: Fractions are parts of a whole."
)
image.save("lesson.png")
```

A profile trajectory is represented as normalized `(x, y)` points. The renderer consumes those trajectories directly, so a future extraction/alignment pipeline can replace individual profile entries without changing the generation path. The bundled default profile is a functional engineering fallback and is not presented as a specific teacher's identity; teacher-specific authenticity requires verified sample trajectories.
