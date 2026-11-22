# Handwritten-text recognition

`model/htr.py` implements the Rank 4 recognition orchestration layer. It accepts a real HTR provider through a small adapter contract and makes the result safe for downstream lesson generation.

For every detected line it returns normalized text, source bounding box, calibrated confidence, provider identity, alternatives, ambiguous-character metadata, and actionable review reasons. Confidence values may be supplied as probabilities or percentages. Empty results, low confidence, competing alternatives, and provider-reported ambiguous characters are never silently accepted.

```python
from model.htr import HTRPipeline

result = HTRPipeline(provider).recognize(page_analysis)
if result.needs_review:
    # Send flagged lines to teacher correction before generation.
    ...
lesson_text = result.text
```

No model is downloaded implicitly and no unavailable provider is replaced with guessed text. A production deployment can inject a trained CTC/Transformer HTR adapter, while tests and local development can use a deterministic fake provider. This keeps the application honest about recognition quality and preserves line-level evidence for correction workflows.
