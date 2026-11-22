# Character extraction and alignment

`model/character_alignment.py` implements Rank 3 for labeled handwriting evidence.

Each accepted character retains:

- the verified Unicode label and original sequence index;
- the label provenance (`worksheet_cell_teacher_confirmation_required` or another explicit verified source);
- source-page bounding box and normalized page coordinates;
- a 96×96 normalized crop for downstream style learning;
- component count, ink ratio, border-touching flag, and a review-oriented quality score.

The aligner rejects guessed labels, empty crops, malformed labels, and samples with too little ink. Duplicate labels are retained as variants rather than overwritten, enabling the style learner to preserve repeated examples. Quality is deliberately a review signal, not a fabricated recognition probability.

```python
from model.character_alignment import CharacterAligner

result = CharacterAligner().align(glyphs_from_verified_worksheet)
for character in result.accepted:
    print(character.label, character.source_bbox, character.quality)
```

This result can feed `WriterStyleLearner` after review. The separation keeps extraction/alignment traceable and prevents a visually plausible but incorrectly labeled sample from contaminating a teacher profile.
