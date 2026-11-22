# Page and handwriting segmentation

`ingestion/segmentation.py` implements Rank 6 for ordinary notebook photos without fixed worksheet rows. It detects a page boundary when a strong enclosing contour is visible, otherwise preserves the full image as the source coordinate system.

The segmenter returns:

- page boundary and confidence;
- variable-count writing-line boxes;
- paragraph groups derived from vertical spacing;
- text regions derived from horizontal ink runs within each line;
- source coordinates and ink ratios for every region;
- warnings when evidence is limited.

```python
from ingestion.segmentation import NotebookSegmenter

segmentation = NotebookSegmenter().segment(image)
for region in segmentation.regions:
    print(region.line_index, region.paragraph_index, region.bbox)
```

Notebook rules are removed before projection analysis, and line/region coordinates remain tied to the original image for later HTR review and character extraction. A blank or nearly blank page is rejected rather than producing fabricated regions.
