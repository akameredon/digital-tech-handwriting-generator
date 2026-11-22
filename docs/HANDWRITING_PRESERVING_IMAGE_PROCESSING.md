# Handwriting-preserving image processing

`ingestion/image_preservation.py` implements Rank 7 for ordinary page captures. It optionally rectifies a detected or explicitly supplied page quadrilateral, applies conservative deskewing, normalizes uneven illumination with a blurred-field correction plus limited CLAHE, and retains a detail score before and after processing.

```python
from ingestion.image_preservation import HandwritingPreserver

corrected, report = HandwritingPreserver().process(photo, corners=page_corners)
print(report.public_dict())
```

The result remains a high-detail grayscale path wrapped as BGR for compatibility with the existing OpenCV ingestion stack. If no page boundary is reliable, the full source coordinate system is preserved and a warning is returned instead of an aggressive crop. Large rotations are not blindly corrected, and the report exposes every transformation for QA.
