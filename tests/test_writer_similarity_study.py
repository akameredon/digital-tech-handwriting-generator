import json
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image, PngImagePlugin

from qa.writer_similarity_study import (
    Assignment,
    Candidate,
    Rating,
    SourcePhrase,
    aggregate_ratings,
    build_manifest,
)


def image(path, number):
    # Metadata and path intentionally reveal identity; neither should be shared.
    info = PngImagePlugin.PngInfo()
    info.add_text("Author", "teacher-secret-1 method-secret-special")
    sample = Image.new("RGB", (8, 8), (number, number * 2, number * 3))
    sample.putpixel((0, 0), (0, 0, 0))
    sample.save(path, pnginfo=info)
    return path


@pytest.fixture
def study_inputs(tmp_path):
    sources = [
        SourcePhrase("source-secret-1", "teacher-secret-1", "Café!  Hello\nworld.",
                     image(tmp_path / "teacher-secret-1-reference.png", 1), True, True),
        SourcePhrase("source-secret-2", "teacher-secret-2", "A distinct phrase.",
                     image(tmp_path / "teacher-secret-2-reference.png", 2), True, True),
        SourcePhrase("source-secret-3", "teacher-secret-1", "Another held-out phrase.",
                     image(tmp_path / "teacher-secret-1-reference-2.png", 3), True, True),
    ]
    candidates = []
    for index, source in enumerate(sources):
        for offset, method in enumerate(("method-secret-generic", "method-secret-special")):
            candidates.append(Candidate(source.source_id, method, source.text,
                                        image(tmp_path / f"{source.source_id}-{method}.png",
                                              4 + index * 2 + offset), True))
    return sources, candidates


def build(tmp_path, inputs, *, suffix="", seed=17):
    sources, candidates = inputs
    return build_manifest(sources, candidates, baseline_method="method-secret-generic",
                          seed=seed, public_dir=tmp_path / ("review" + suffix),
                          private_key_path=tmp_path / ("key" + suffix + ".json"))


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def candidate_id(key, source, method):
    return next(c["candidate_id"] for c in key["candidates"]
                if c["source_id"] == source and c["method"] == method)


def test_public_package_is_blinded_and_private_key_is_separate(study_inputs, tmp_path):
    paths = build(tmp_path, study_inputs)
    manifest, key = load(paths.manifest_path), load(paths.private_key_path)
    assert paths.private_key_path.parent != paths.public_dir
    assert paths.private_key_path.stat().st_mode & 0o777 == 0o600
    assert paths.public_dir.stat().st_mode & 0o077 == 0
    assert (paths.public_dir / "assets").stat().st_mode & 0o077 == 0
    assert set(manifest) == {"schema_version", "references", "candidates", "label_options", "score_scale", "protocol"}
    assert "before consulting" in manifest["protocol"][0]
    assert len(manifest["references"]) == 3
    assert len(manifest["candidates"]) == 6
    assert {s["teacher_id"] for s in key["sources"]} == {s.teacher_id for s in study_inputs[0]}
    assert {s["text"] for s in key["sources"]} == {s.text for s in study_inputs[0]}
    assert key["baseline_method"] == "method-secret-generic"
    assert key["seed"] == 17
    public_json = paths.manifest_path.read_text(encoding="utf-8")
    for forbidden in ("teacher-secret", "source-secret", "method-secret", "Café", str(tmp_path),
                      "baseline", '"seed"', "input_image", "pixel_sha256"):
        assert forbidden not in public_json
    reference_ids = {r["reference_id"] for r in manifest["references"]}
    candidate_ids = {c["candidate_id"] for c in manifest["candidates"]}
    assert len(candidate_ids) == 6 and not candidate_ids & reference_ids
    assert all(set(r) == {"reference_id", "image"} for r in manifest["references"])
    assert all(set(c) == {"candidate_id", "reference_id", "image"} for c in manifest["candidates"])
    for item in manifest["references"] + manifest["candidates"]:
        ident = item.get("candidate_id", item.get("reference_id"))
        assert item["image"] == f"assets/{ident}.png"
        with Image.open(paths.public_dir / item["image"]) as result:
            assert result.info == {}
            assert result.format == "PNG"
            assert result.mode == "RGB"
    assert not any(p.name.endswith(".json") and p.name != "manifest.json"
                   for p in paths.public_dir.rglob("*"))


def test_seed_reproducibility_order_independence_and_randomization(study_inputs, tmp_path):
    a = build(tmp_path, study_inputs, suffix="-a", seed=17)
    b = build(tmp_path, (list(reversed(study_inputs[0])), list(reversed(study_inputs[1]))),
              suffix="-b", seed=17)
    c = build(tmp_path, study_inputs, suffix="-c", seed=78)
    assert a.manifest_path.read_bytes() == b.manifest_path.read_bytes()
    assert a.private_key_path.read_bytes() == b.private_key_path.read_bytes()
    assert {p.name: p.read_bytes() for p in (a.public_dir / "assets").iterdir()} == {
        p.name: p.read_bytes() for p in (b.public_dir / "assets").iterdir()}
    assert load(a.manifest_path) != load(c.manifest_path)
    key_a, key_c = load(a.private_key_path), load(c.private_key_path)
    order_a = [(x["source_id"], x["method"]) for x in key_a["candidates"]]
    order_c = [(x["source_id"], x["method"]) for x in key_c["candidates"]]
    assert order_a != order_c
    assert {x["candidate_id"] for x in key_a["candidates"]}.isdisjoint(
        {x["candidate_id"] for x in key_c["candidates"]})


@pytest.mark.parametrize("bad_text", ["Café! Hello\nworld.", "café!  Hello\nworld.",
                                      "Cafe\u0301!  Hello\nworld.", "Café!  Hello\nworld. "])
def test_requires_exact_not_normalized_text(study_inputs, tmp_path, bad_text):
    sources, candidates = study_inputs
    candidates[0] = replace(candidates[0], text=bad_text)
    with pytest.raises(ValueError, match="exactly match"):
        build(tmp_path, (sources, candidates))
    assert not (tmp_path / "review").exists()
    assert not (tmp_path / "key.json").exists()


@pytest.mark.parametrize("change, message", [
    ("no_sources", "at least one"),
    ("no_candidates", "at least one"),
    ("unverified", "verified and held out"),
    ("not_held_out", "verified and held out"),
    ("truthy_not_verified", "verified and held out"),
    ("blank_text", "source text"),
    ("blank_teacher", "teacher_id"),
    ("duplicate_source", "duplicate source_id"),
    ("duplicate_phrase", "duplicate teacher and source text"),
    ("unknown_source", "unknown source"),
    ("candidate_unverified", "independently verified"),
    ("duplicate_candidate", "duplicate candidate"),
    ("missing_baseline", "baseline and at least one"),
    ("missing_comparator", "baseline and at least one"),
    ("unbalanced", "same methods"),
    ("missing_image", "cannot be read"),
    ("bad_image", "cannot be read"),
    ("blank_image", "blank or uniform"),
    ("duplicate_path", "duplicate image"),
    ("duplicate_pixels", "duplicate image"),
    ("duplicate_rgba_pixels", "duplicate image"),
])
def test_invalid_inputs_fail_without_creating_outputs(study_inputs, tmp_path, change, message):
    sources, candidates = study_inputs
    if change == "no_sources": sources = []
    if change == "no_candidates": candidates = []
    if change == "unverified": sources[0] = replace(sources[0], verified=False)
    if change == "not_held_out": sources[0] = replace(sources[0], held_out=False)
    if change == "truthy_not_verified": sources[0] = replace(sources[0], verified=1)
    if change == "blank_text": sources[0] = replace(sources[0], text="  ")
    if change == "blank_teacher": sources[0] = replace(sources[0], teacher_id=" ")
    if change == "duplicate_source": sources.append(sources[0])
    if change == "duplicate_phrase": sources.append(replace(sources[0], source_id="another-id"))
    if change == "unknown_source": candidates[0] = replace(candidates[0], source_id="unknown")
    if change == "candidate_unverified": candidates[0] = replace(candidates[0], text_verified=False)
    if change == "duplicate_candidate": candidates.append(candidates[0])
    if change == "missing_baseline": candidates.pop(0)
    if change == "missing_comparator": candidates.pop(1)
    if change == "unbalanced":
        candidates.append(Candidate(sources[0].source_id, "third method", sources[0].text,
                                    image(tmp_path / "third.png", 20), True))
    if change == "missing_image": candidates[0] = replace(candidates[0], image_path=tmp_path / "missing.png")
    if change == "bad_image":
        (tmp_path / "bad.png").write_text("not an image")
        candidates[0] = replace(candidates[0], image_path=tmp_path / "bad.png")
    if change == "blank_image":
        Image.new("RGB", (8, 8), "white").save(tmp_path / "blank.png")
        candidates[0] = replace(candidates[0], image_path=tmp_path / "blank.png")
    if change == "duplicate_path": candidates[0] = replace(candidates[0], image_path=sources[0].image_path)
    if change == "duplicate_pixels":
        image(tmp_path / "duplicate.png", 1)
        candidates[0] = replace(candidates[0], image_path=tmp_path / "duplicate.png")
    if change == "duplicate_rgba_pixels":
        with Image.open(sources[0].image_path) as source:
            source.convert("RGBA").save(tmp_path / "duplicate-rgba.png")
        candidates[0] = replace(candidates[0], image_path=tmp_path / "duplicate-rgba.png")
    with pytest.raises(ValueError, match=message):
        build(tmp_path, (sources, candidates))
    assert not (tmp_path / "review").exists()
    assert not (tmp_path / "key.json").exists()


def test_invisible_transparent_payloads_do_not_evade_duplicate_check(study_inputs, tmp_path):
    sources, candidates = study_inputs
    for index, secret in enumerate(((65, 66, 67, 0), (68, 69, 70, 0))):
        sample = Image.new("RGBA", (8, 8), (255, 255, 255, 255))
        sample.putpixel((0, 0), (0, 0, 0, 255))
        sample.putpixel((1, 1), secret)
        path = tmp_path / f"transparent-{index}.png"
        sample.save(path)
        candidates[index] = replace(candidates[index], image_path=path)
    with pytest.raises(ValueError, match="duplicate image"):
        build(tmp_path, (sources, candidates))
    assert not (tmp_path / "review").exists()
    assert not (tmp_path / "key.json").exists()


def test_transparent_pixels_are_published_as_visible_white_only(study_inputs, tmp_path):
    sources, candidates = study_inputs
    sample = Image.new("RGBA", (8, 8), (255, 255, 255, 255))
    sample.putpixel((0, 0), (0, 0, 0, 255))
    sample.putpixel((1, 1), (65, 66, 67, 0))
    path = tmp_path / "transparent.png"
    sample.save(path)
    candidates[0] = replace(candidates[0], image_path=path)
    paths = build(tmp_path, (sources, candidates))
    key, manifest = load(paths.private_key_path), load(paths.manifest_path)
    cid = candidate_id(key, candidates[0].source_id, candidates[0].method)
    asset = next(c["image"] for c in manifest["candidates"] if c["candidate_id"] == cid)
    with Image.open(paths.public_dir / asset) as output:
        assert output.mode == "RGB"
        assert output.getpixel((1, 1)) == (255, 255, 255)


def test_identity_bearing_expected_text_stays_private(study_inputs, tmp_path):
    sources, candidates = study_inputs
    text = "About teacher-secret-2 and method-secret-generic"
    sources[0] = replace(sources[0], text=text)
    candidates = [replace(c, text=text) if c.source_id == sources[0].source_id else c for c in candidates]
    paths = build(tmp_path, (sources, candidates))
    assert text not in paths.manifest_path.read_text(encoding="utf-8")
    assert any(s["text"] == text for s in load(paths.private_key_path)["sources"])


def test_prevents_private_key_under_public_dir_and_preexisting_overwrites(study_inputs, tmp_path):
    with pytest.raises(ValueError, match="outside"):
        build_manifest(*study_inputs, baseline_method="method-secret-generic", seed=1,
                       public_dir=tmp_path / "out", private_key_path=tmp_path / "out" / "key.json")
    assert not (tmp_path / "out").exists()
    (tmp_path / "review").mkdir()
    (tmp_path / "review" / "important").write_text("unchanged")
    with pytest.raises(ValueError, match="must not already exist"):
        build(tmp_path, study_inputs)
    assert (tmp_path / "review" / "important").read_text() == "unchanged"
    assert not (tmp_path / "key.json").exists()


def test_seed_type_and_output_parent_validation(study_inputs, tmp_path):
    with pytest.raises(ValueError, match="seed"):
        build(tmp_path, study_inputs, seed=True)
    with pytest.raises(ValueError, match="parents"):
        build_manifest(*study_inputs, baseline_method="method-secret-generic", seed=1,
                       public_dir=tmp_path / "missing" / "out", private_key_path=tmp_path / "key.json")


def test_failed_write_does_not_leave_partial_public_package(study_inputs, tmp_path, monkeypatch):
    def fail_write(self, data):
        raise OSError("simulated storage failure")
    monkeypatch.setattr(Path, "write_bytes", fail_write)
    with pytest.raises(OSError, match="simulated storage failure"):
        build(tmp_path, study_inputs)
    assert not (tmp_path / "review").exists()
    assert not (tmp_path / "key.json").exists()


def test_aggregation_metrics_missingness_and_paired_baseline(study_inputs, tmp_path):
    paths = build(tmp_path, study_inputs)
    key = load(paths.private_key_path)
    base, special = "method-secret-generic", "method-secret-special"
    def cid(n, method): return candidate_id(key, f"source-secret-{n}", method)
    rows = [
        Rating(cid(1, base), "r1", "same_writer", 2, 2),
        Rating(cid(1, base), "r2", "different_writer", 4, 4),
        Rating(cid(1, special), "r1", "same_writer", 4, 5),
        Rating(cid(1, special), "r2", "same_writer", 5, 4),
        Rating(cid(2, base), "r1", "unsure", 3, 3),
        Rating(cid(2, special), "r1", "different_writer", 1, 2),
        Rating(cid(2, special), "r2", "same_writer", 5, None),
        Rating(cid(3, base), "r1", "different_writer", None, 1),
        Rating(cid(3, base), "r2", None, 5, 3),
        Rating(cid(3, special), "r2", "unsure", 3, 2),
    ]
    report = aggregate_ratings(paths.private_key_path, ["r1", "r2"], rows)
    overall = report["overall"]
    assert overall["candidate_count"] == 6
    assert overall["source_count"] == 3
    assert overall["teacher_count"] == 2
    assert overall["expected_rating_rows"] == 12
    assert overall["submitted_rating_rows"] == 10
    assert overall["missing_rating_rows"] == 2
    assert overall["missing_by_field"] == {"label": 3, "legibility": 3, "similarity": 3}
    group = report["by_method"][special]
    assert group["candidate_count"] == 3
    assert group["labels"]["counts"] == {"same_writer": 3, "different_writer": 1, "unsure": 1}
    assert group["labels"]["proportions"]["same_writer"] == pytest.approx(3 / 5)
    assert group["legibility"]["n"] == 5
    assert group["legibility"]["mean"] == pytest.approx(3.6)
    assert group["similarity"]["mean"] == pytest.approx(3.25)
    assert group["inter_rater"]["label"] == {
        "items_with_2_plus_ratings": 2, "rater_pairs": 2,
        "exact_agreements": 1, "exact_agreement_rate": 0.5}
    assert group["inter_rater"]["similarity"]["rater_pairs"] == 1
    assert group["inter_rater"]["similarity"]["mean_absolute_difference"] == 1
    assert report["by_method_teacher"][special]["teacher-secret-1"]["candidate_count"] == 2
    assert report["by_teacher"]["teacher-secret-2"]["candidate_count"] == 2
    paired = report["paired_vs_baseline"][special]["overall"]
    assert paired["expected_source_reviewer_pairs"] == 6
    assert paired["matched_source_reviewer_pairs"] == 4
    assert paired["missing_paired_submissions"] == 2
    assert paired["similarity"]["n"] == 4
    assert paired["similarity"]["mean_method_minus_baseline"] == pytest.approx(0.25)
    assert paired["legibility"]["mean_method_minus_baseline"] == pytest.approx(-0.25)
    assert paired["labels"]["n"] == 3
    assert paired["labels"]["same_writer_rate_difference"] == pytest.approx(1 / 3)
    assert paired["labels"]["method_by_baseline"]["same_writer"]["different_writer"] == 1
    assert report["paired_vs_baseline"][special]["by_teacher"]["teacher-secret-2"]["matched_source_reviewer_pairs"] == 1
    assert aggregate_ratings(paths.private_key_path, ["r1", "r2"], list(reversed(rows))) == report
    assert 'passed' not in json.dumps(report)


def test_assignments_missing_data_and_empty_metrics(study_inputs, tmp_path):
    paths = build(tmp_path, study_inputs)
    key = load(paths.private_key_path)
    cid = key["candidates"][0]["candidate_id"]
    report = aggregate_ratings(paths.private_key_path, ["r1", "r2"], [Rating(cid, "r1")],
                               assignments=[Assignment(cid, "r1"), Assignment(cid, "r2")])
    assert report["overall"]["candidate_count"] == 6
    assert report["overall"]["unassigned_candidates"] == 5
    assert report["overall"]["expected_rating_rows"] == 2
    assert report["overall"]["submitted_rating_rows"] == 1
    assert report["overall"]["missing_rating_rows"] == 1
    assert report["overall"]["missing_by_field"] == {"label": 2, "legibility": 2, "similarity": 2}
    assert report["overall"]["labels"]["proportions"]["same_writer"] is None
    assert report["overall"]["legibility"]["mean"] is None
    assert report["overall"]["inter_rater"]["label"]["exact_agreement_rate"] is None


def test_inter_rater_uses_all_unordered_pairs_for_three_reviewers(study_inputs, tmp_path):
    paths = build(tmp_path, study_inputs)
    cid = load(paths.private_key_path)["candidates"][0]["candidate_id"]
    rows = [Rating(cid, "r1", "same_writer", 1, 1),
            Rating(cid, "r2", "same_writer", 3, 1),
            Rating(cid, "r3", "unsure", 5, 4)]
    report = aggregate_ratings(paths.private_key_path, ["r1", "r2", "r3"], rows,
                               assignments=[Assignment(cid, r) for r in ("r1", "r2", "r3")])
    labels = report["overall"]["inter_rater"]["label"]
    assert labels["items_with_2_plus_ratings"] == 1
    assert labels["rater_pairs"] == 3
    assert labels["exact_agreement_rate"] == pytest.approx(1 / 3)
    legibility = report["overall"]["inter_rater"]["legibility"]
    assert legibility["rater_pairs"] == 3
    assert legibility["mean_absolute_difference"] == pytest.approx(8 / 3)


@pytest.mark.parametrize("case", ["duplicate_reviewer", "empty_reviewers", "unknown_candidate",
                                  "unknown_reviewer", "duplicate_rating", "bad_label", "bad_score",
                                  "bool_score", "fractional_score", "nan_score", "duplicate_assignment",
                                  "unknown_assignment", "unassigned_rating", "empty_assignments"])
def test_rejects_unknown_duplicate_and_invalid_ratings(study_inputs, tmp_path, case):
    paths = build(tmp_path, study_inputs)
    cid = load(paths.private_key_path)["candidates"][0]["candidate_id"]
    row = Rating(cid, "r1", "same_writer", 3, 4)
    reviewers, rows, assignments = ["r1", "r2"], [row], None
    if case == "duplicate_reviewer": reviewers = ["r1", "r1"]
    if case == "empty_reviewers": reviewers = []
    if case == "unknown_candidate": rows = [replace(row, candidate_id="unknown")]
    if case == "unknown_reviewer": rows = [replace(row, reviewer_id="unknown")]
    if case == "duplicate_rating": rows = [row, row]
    if case == "bad_label": rows = [replace(row, label="genuine")]
    if case == "bad_score": rows = [replace(row, similarity=6)]
    if case == "bool_score": rows = [replace(row, legibility=True)]
    if case == "fractional_score": rows = [replace(row, similarity=3.5)]
    if case == "nan_score": rows = [replace(row, similarity=float('nan'))]
    if case == "duplicate_assignment": assignments = [Assignment(cid, "r1"), Assignment(cid, "r1")]
    if case == "unknown_assignment": assignments = [Assignment("unknown", "r1")]
    if case == "unassigned_rating": assignments = [Assignment(cid, "r2")]
    if case == "empty_assignments": assignments = []
    with pytest.raises(ValueError):
        aggregate_ratings(paths.private_key_path, reviewers, rows, assignments=assignments)


def test_key_tampering_unknown_and_duplicate_records_are_rejected(study_inputs, tmp_path):
    paths = build(tmp_path, study_inputs)
    original = load(paths.private_key_path)
    for mutation in ("duplicate_candidate", "unknown_source", "changed_text", "missing_baseline"):
        key = json.loads(json.dumps(original))
        if mutation == "duplicate_candidate": key["candidates"].append(key["candidates"][0])
        if mutation == "unknown_source": key["candidates"][0]["source_id"] = "unknown"
        if mutation == "changed_text": key["candidates"][0]["text"] += " "
        if mutation == "missing_baseline": key["baseline_method"] = "not-a-method"
        altered = tmp_path / f"{mutation}.json"
        altered.write_text(json.dumps(key))
        with pytest.raises(ValueError):
            aggregate_ratings(altered, ["r1"], [])
