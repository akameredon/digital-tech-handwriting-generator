# Stroke-handwriting prototypes

Convincing generation of a particular teacher's handwriting for unseen words and lesson notes remains an open research and validation challenge. Neither prototype below establishes writer identity, natural connections, or real-world handwriting fidelity. The project must not describe a partial character profile or an attractive PDF as a completed handwriting intelligence system.

## Legacy renderer

`renderer/stroke_handwriting.py` renders manually specified coordinate paths without using an installed font. The built-in paths are generic shapes, not recordings of a teacher's pen motion. Missing characters can silently fall back to these shapes, uppercase letters can fall back to lowercase paths, punctuation has synthetic handling, and long lines can be truncated. Its variable widths, placement and joins are heuristics, not learned teacher-specific dynamics. It is a prototype, not an authentic handwriting solution.

The existing legacy API is retained for compatibility:

```python
from renderer.stroke_handwriting import HandwritingRenderer, WriterProfile

profile = WriterProfile.load("teacher.json")
image = HandwritingRenderer(profile, seed=2025).render("Hello, class.")
image.save("lesson.png")
```

A profile stores paths as normalized `(x, y)` points, but merely providing a profile does not verify its provenance or its coverage. Do not use the legacy renderer to test exact-character coverage or complete lesson output.

## Experimental sample-backed renderer

`renderer/teacher_stroke_generation.py` is a separate, bounded experiment. It renders only explicitly supplied per-character paths, fails on unsupported input instead of substituting a font or generic glyph, and wraps and paginates within resource limits. Joins are disabled by default; opt-in endpoint joins are explicitly synthetic. `model/teacher_ink.py` can trace geometric skeletons from explicitly confirmed calibration-sheet crops, but static ink does not recover pen order, pressure, baseline or writer identity. These are geometric approximations, not learned handwriting intelligence.

For the isolated local worksheet-to-PDF experiment, see [EXPERIMENTAL_WRITER_PDF.md](EXPERIMENTAL_WRITER_PDF.md). Before any authenticity claim, collect consensually provided real teacher writing, hold out independently transcribed phrases, and compare generated samples with genuine and generic baselines through independent blinded assessment. No such result is bundled with this repository.
