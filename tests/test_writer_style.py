import cv2
import numpy as np

from model.writer_style import VerifiedGlyphSample, WriterStyleLearner
from renderer.stroke_handwriting import WriterProfile


def glyph_image(kind: str = "a"):
    image = np.full((80, 60), 255, dtype=np.uint8)
    if kind == "a":
        cv2.line(image, (8, 55), (22, 20), 0, 4)
        cv2.line(image, (22, 20), (42, 55), 0, 4)
        cv2.line(image, (14, 40), (36, 40), 0, 4)
    else:
        cv2.line(image, (10, 55), (30, 12), 0, 5)
        cv2.line(image, (30, 12), (48, 55), 0, 5)
    return image


def test_learns_trajectory_profile_and_reports_incomplete_coverage():
    learner = WriterStyleLearner(required_characters="ab")
    result = learner.fit([
        VerifiedGlyphSample("a", glyph_image("a")),
        VerifiedGlyphSample("b", glyph_image("b")),
    ], writer_name="teacher-a")
    assert result.profile.name == "teacher-a"
    assert set(result.coverage) == {"a", "b"}
    assert result.missing == []
    assert result.profile.glyph("a")
    assert result.coverage_ratio == 1.0


def test_low_confidence_samples_are_not_used_as_identity():
    result = WriterStyleLearner(required_characters="ab").fit([
        VerifiedGlyphSample("a", glyph_image(), confidence=0.99),
        VerifiedGlyphSample("b", glyph_image(), confidence=0.30),
    ])
    assert "b" in result.missing
    assert any("low-confidence" in warning for warning in result.warnings)


def test_learned_profile_can_be_saved_and_reloaded(tmp_path):
    result = WriterStyleLearner(required_characters="a").fit([
        VerifiedGlyphSample("a", glyph_image()),
    ])
    path = tmp_path / "teacher.json"
    result.profile.save(path)
    loaded = WriterProfile.load(path)
    assert loaded.name == "learned-writer"
    assert loaded.glyph("a") == result.profile.glyph("a")
