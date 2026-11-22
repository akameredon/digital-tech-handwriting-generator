import cv2
import numpy as np

from model.writer_style import VerifiedGlyphSample, WriterStyleLearner
from model.profile_management import ManagedWriterProfile, WriterProfileStore
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
    assert result.evidence["a"] == {
        "sample_count": 1,
        "mean_confidence": 1.0,
        "sources": ["verified"],
    }


def test_repeated_samples_are_available_as_distinct_seedable_variants():
    result = WriterStyleLearner(required_characters="a").fit([
        VerifiedGlyphSample("a", glyph_image("a"), source="page-1"),
        VerifiedGlyphSample("a", glyph_image("b"), source="page-2"),
    ])

    assert len(result.profile.variants["a"]) == 2
    assert result.profile.glyph("a", variant_index=0) != result.profile.glyph("a", variant_index=1)


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


def test_profile_store_merges_new_verified_variants_and_evidence(tmp_path):
    learner = WriterStyleLearner(required_characters="a")
    first = learner.fit([VerifiedGlyphSample("a", glyph_image(), confidence=0.80, source="page-1")])
    second = learner.fit([VerifiedGlyphSample("a", glyph_image("b"), confidence=1.0, source="page-2")])
    store = WriterProfileStore(tmp_path)
    managed = ManagedWriterProfile(first.profile, evidence=dict(first.evidence))

    store.merge_learning(managed, second)
    assert len(managed.profile.strokes["a"]) == 2
    assert len(managed.profile.variants["a"]) == 2
    assert managed.evidence["a"]["sample_count"] == 2
    assert managed.evidence["a"]["sources"] == ["page-1", "page-2"]
    assert managed.approved is False

    store.save(managed)
    reloaded = store.load("learned-writer")
    assert reloaded.evidence["a"]["sample_count"] == 2
    assert len(reloaded.profile.variants["a"]) == 2
