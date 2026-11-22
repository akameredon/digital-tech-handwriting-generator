# Writer-style learning and reconstruction

`model/writer_style.py` implements experimental static-image geometry learning. It reports coverage rather than treating an incomplete profile as complete. Image geometry and statistical estimates are experimental: a static raster cannot establish pen order, true pressure, or verified teacher likeness.

## Pipeline
1. Accept `VerifiedGlyphSample` values (the class represents caller attestation), or mappings with an explicit boolean `verified: true` (or `attested: true`) **and** a recognized trusted source (`verified`, `teacher`, `trusted_worksheet`, `worksheet_position`, or `human_verified`). This is an assertion by the caller, not cryptographic proof. Mappings without both are skipped with a warning and do not contribute coverage.
2. Reject malformed/low-confidence samples and validate finite pixels, supported 2D grayscale/1/3/4-channel dimensions, and a 16-million-pixel-per-image cap. Processing is also bounded to 2,048 input samples and 64 million total pixel values per fit.
3. Extract a normalized center trajectory and estimate experimental scale, slant, stroke width, and density-derived pressure proxy from tight ink crops. Padding around the same drawing does not affect these estimates.
4. Retain every accepted normalized trajectory, in input order, under `StyleLearningResult.variants`. Alternatives are separate samples, never combined into one profile glyph, since that would render all strokes simultaneously. The legacy `WriterProfile` remains unchanged and contains the first accepted trajectory as its primary profile glyph.
5. Keep coverage counts and missing characters so the application can request more evidence instead of fabricating confidence.

```python
from model.writer_style import VerifiedGlyphSample, WriterStyleLearner
result = WriterStyleLearner().fit(samples, writer_name="Mrs Okafor")
result.profile.save("mrs-okafor.json")  # legacy primary profile only
result.save_artifact("mrs-okafor-learning.json")  # versioned profile + all alternatives
restored = type(result).load_artifact("mrs-okafor-learning.json")
```

`save_artifact`/`load_artifact` use version 1 and preserve alternatives, profile, coverage, and warnings. A caller can select a variant later; the renderer is not changed to combine alternatives.
