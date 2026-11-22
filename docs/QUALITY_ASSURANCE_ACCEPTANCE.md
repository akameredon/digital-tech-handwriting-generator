# Quality assurance and real-world acceptance

`qa/acceptance.py` implements Rank 10 as independent acceptance gates rather than a single visual check. It scores recognition with character error rate and word accuracy, compares reference and generated handwriting structure plus ink density, validates complete lesson structure, and checks that a generated PDF has pages, extractable text, and valid printable page boxes.

```python
from qa.acceptance import AcceptanceEvaluator

report = AcceptanceEvaluator().evaluate(
    expected_text=expected, recognized_text=recognized,
    reference_image=reference, generated_image=generated,
    lesson_text=lesson, pdf_path="lesson.pdf",
)
assert report.passed, report.public_dict()
```

Missing evidence fails its corresponding gate instead of passing by default. The report is serializable for CI, release checks, and teacher acceptance reviews.
