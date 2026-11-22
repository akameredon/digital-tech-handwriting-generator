# Complete lesson-content generation

`curriculum/lesson_generator.py` implements Rank 8 as a deterministic, curriculum-bounded lesson generator. It reads the official class, term, week, topic, and content breakdown, then produces a coherent note with:

- metadata and topic fidelity;
- measurable behavioral objectives;
- key concepts and definitions;
- step-by-step conceptual explanation;
- practical/worked example;
- class activity and guided practice;
- five-question quick test;
- take-home assignment.

The generated Markdown is passed through the existing lesson validator before the convenience API returns it. Unknown curriculum weeks return `None` rather than fabricated content.

```python
from curriculum.lesson_generator import generate_complete_lesson

note = generate_complete_lesson("SS2", "Second Term", 2)
```
