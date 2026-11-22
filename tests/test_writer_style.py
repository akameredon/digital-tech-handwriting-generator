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
    result = learner.fit(
        [
            VerifiedGlyphSample("a", glyph_image("a")),
            VerifiedGlyphSample("b", glyph_image("b")),
        ],
        writer_name="teacher-a",
    )
    assert result.profile.name == "teacher-a"
    assert set(result.coverage) == {"a", "b"}
    assert result.missing == []
    assert result.profile.glyph("a")
    assert result.coverage_ratio == 1.0


def test_low_confidence_samples_are_not_used_as_identity():
    result = WriterStyleLearner(required_characters="ab").fit(
        [
            VerifiedGlyphSample("a", glyph_image(), confidence=0.99),
            VerifiedGlyphSample("b", glyph_image(), confidence=0.30),
        ]
    )
    assert "b" in result.missing
    assert any("low-confidence" in warning for warning in result.warnings)


def test_learned_profile_can_be_saved_and_reloaded(tmp_path):
    result = WriterStyleLearner(required_characters="a").fit(
        [
            VerifiedGlyphSample("a", glyph_image()),
        ]
    )
    path = tmp_path / "teacher.json"
    result.profile.save(path)
    loaded = WriterProfile.load(path)
    assert loaded.name == "learned-writer"
    assert loaded.glyph("a") == result.profile.glyph("a")


def test_mapping_requires_explicit_attestation_and_trusted_source_aliases():
    image = glyph_image()
    learner = WriterStyleLearner(required_characters="ab")
    result = learner.fit(
        [
            {"label": "a", "image": image, "source": "machine_guess"},
            {"label": "b", "image": image, "source": "teacher", "verified": True},
        ]
    )
    assert result.coverage == {"b": 1}
    assert "a" in result.missing
    assert any("attestation" in w for w in result.warnings)
    alias = learner.fit(
        [{"label": "a", "image": image, "label_source": "trusted_worksheet", "attested": True}]
    )
    assert alias.coverage["a"] == 1
    bad = learner.fit([{"label": "a", "image": image, "source": "machine_guess", "verified": True}])
    assert bad.coverage == {}


def test_variants_remain_separate_ordered_and_round_trip(tmp_path):
    first, second = glyph_image("a"), glyph_image("b")
    result = WriterStyleLearner(required_characters="a").fit(
        [
            VerifiedGlyphSample("a", first),
            VerifiedGlyphSample("a", second),
            VerifiedGlyphSample("a", first),
        ]
    )
    assert result.coverage["a"] == 3
    assert len(result.variants["a"]) == 3
    assert result.variants["a"][0] == result.variants["a"][2]
    assert result.variants["a"][0] != result.variants["a"][1]
    assert result.profile.glyph("a") == [result.variants["a"][0]]
    path = tmp_path / "learning.json"
    result.save_artifact(path)
    restored = type(result).load_artifact(path)
    assert restored.variants == result.variants
    assert restored.coverage == result.coverage
    assert restored.profile.glyph("a") == result.profile.glyph("a")


def test_stats_and_trajectory_are_invariant_to_canvas_padding():
    image = glyph_image()
    padded = np.full((220, 190), 255, dtype=np.uint8)
    padded[70:150, 55:115] = image
    learner = WriterStyleLearner(required_characters="a")
    one = learner.fit([VerifiedGlyphSample("a", image)])
    two = learner.fit([VerifiedGlyphSample("a", padded)])
    assert one.profile.scale == two.profile.scale
    assert one.profile.slant == two.profile.slant
    assert one.profile.stroke_width == two.profile.stroke_width
    assert one.profile.pressure == two.profile.pressure
    assert one.profile.glyph("a") == two.profile.glyph("a")


def test_validation_rejects_nonfinite_confidence_bad_images_and_constructor_values():
    import pytest

    for bad in (float("nan"), float("inf"), True, -0.1, 1.1):
        with pytest.raises(ValueError):
            VerifiedGlyphSample("a", glyph_image(), confidence=bad)
    for bad in (float("nan"), float("inf"), True, -1, 1.1):
        with pytest.raises(ValueError):
            WriterStyleLearner(min_confidence=bad)
    with pytest.raises(ValueError):
        VerifiedGlyphSample("\n", glyph_image())
    with pytest.raises(ValueError):
        VerifiedGlyphSample(" ", glyph_image())
    with pytest.raises(ValueError):
        VerifiedGlyphSample("a", glyph_image(), source="machine_guess")
    with pytest.raises(ValueError):
        VerifiedGlyphSample("a", np.zeros((2, 2, 2), np.uint8))
    with pytest.raises(ValueError):
        VerifiedGlyphSample("a", np.full((2, 2), np.nan))
    result = WriterStyleLearner(required_characters="a").fit(
        [{"label": "a", "image": None, "verified": True, "source": "teacher"}]
    )
    assert result.coverage == {}
    import pytest

    with pytest.raises(ValueError):
        WriterStyleLearner().fit([], writer_name="  ")
