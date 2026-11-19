"""Basic smoke tests for the handwriting preprocessor."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ingestion.preprocessor import HandwritingPreprocessor, DEFAULT_SAMPLE_ORDER

def test_preprocessor_init():
    pp = HandwritingPreprocessor()
    assert pp.min_contour_area >= 12
    assert pp.padding >= 4

def test_default_sample_order():
    assert "A" in DEFAULT_SAMPLE_ORDER
    assert "z" in DEFAULT_SAMPLE_ORDER
    assert "0" in DEFAULT_SAMPLE_ORDER
    assert len(DEFAULT_SAMPLE_ORDER) == 77

def test_binarize_shape():
    import numpy as np
    pp = HandwritingPreprocessor()
    img = np.ones((100, 200), dtype=np.uint8) * 255
    img[40:60, 50:150] = 0
    binary = pp.binarize(img)
    assert binary.shape == img.shape
    assert binary.dtype == np.uint8
