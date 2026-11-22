# Natural handwriting variation

`model/handwriting_variation.py` implements Rank 5. `NaturalVariationController` applies bounded, correlated realization changes to trajectories: size, slant, baseline, pressure appearance, and connection offset. The whole glyph shares a coherent sample-level field, so variation changes the handwriting naturally without corrupting the character identity.

`VariationMetrics` provides a QA gate over repeated seeded realizations. It measures scale, slant, baseline, and pressure spread, counts distinct outputs, and exposes `healthy` so a renderer test can detect stamped/repetitive output.

```python
from model.handwriting_variation import NaturalVariationController

controller = NaturalVariationController()
metrics = controller.measure(strokes, range(32))
assert metrics.healthy
realization = controller.realize(strokes, seed=2025)
```

The existing renderer already applies realization-level randomness during page rendering; this controller makes the policy explicit, reusable, and testable. A zero-jitter configuration intentionally fails the natural-variation gate, preventing a visually repetitive generator from being treated as authentic.
