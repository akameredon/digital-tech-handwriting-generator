# Character extraction and alignment

The alignment layer separates **model candidates** from **trusted observations**.

A line transcript alone is not enough to create a glyph. The recognizer must return one explicit character box per non-whitespace character. The aligner rejects missing geometry, malformed boxes, count mismatches, out-of-bounds boxes, empty crops, and low-confidence candidates. It never assigns labels by component order or horizontal position.

```python
from model.character_alignment import CharacterAligner

result = CharacterAligner().align_recognized_line(
    line_image,
    line_bbox,
    {
        "text": "Hello",
        "character_boxes": [
            {"bbox": [10, 4, 12, 24], "confidence": 0.98},
            # one entry for each non-space character
        ],
    },
)
```

Candidates remain pending until the teacher confirms the label. Only the explicit confirmation path creates `CharacterObservation` records with verified provenance that can be passed to writer-profile or font-compilation code.

`model/glyph_alignment_pipeline.py` now connects `HTRDocumentResult` to this
gate. Provider-supplied character geometry is preserved through `model/htr.py`
and passed to the aligner. If the provider returns only line text, the bridge
returns a localized `character_geometry_missing` review result. It never
reconstructs character boxes from transcript order, connected-component order,
or x-position.

The current TrOCR adapter is line-level and does not provide character geometry. Therefore it can support transcription and benchmarking, but it must not be used by itself for personalized glyph extraction. A future recognizer or alignment model must implement the geometry portion of the contract before natural-page glyph learning can be enabled.
