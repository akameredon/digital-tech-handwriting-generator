# Writer-style learning and reconstruction

`model/writer_style.py` implements Rank 2: learning a reusable writer identity from limited, verified samples without silently turning an incomplete alphabet into a finished profile.

## Pipeline

1. Accept only labeled samples whose label is verified by the teacher or a trusted worksheet position.
2. Reject low-confidence and empty samples.
3. Convert each crop into a normalized pen trajectory, preserving the sample's proportions and detached marks.
4. Estimate writer-level scale, slant, stroke width, and pressure variation from robust sample medians.
5. Keep coverage counts and missing characters so the application can request more evidence instead of fabricating confidence.
6. Export a `WriterProfile` consumed directly by `HandwritingRenderer` for unseen words and lesson notes.

```python
from model.writer_style import VerifiedGlyphSample, WriterStyleLearner

result = WriterStyleLearner().fit(samples, writer_name="Mrs Okafor")
result.profile.save("mrs-okafor.json")
print(result.public_dict())
```

Repeated samples of the same character are retained as complete glyph variants. The renderer selects them with its seeded random generator, so repeated lesson renders can vary naturally while remaining reproducible for a given seed. Each learning result also records per-glyph sample count, mean confidence, and evidence sources.

`WriterProfileStore.merge_learning()` adds later confirmed variants without replacing earlier evidence, combines confidence metadata, marks the profile unapproved again, and persists the updated version atomically. This is the progressive-profile path used by the natural-page confirmation endpoint. Unobserved characters remain absent and continue to use the renderer's explicit fallback trajectory.
