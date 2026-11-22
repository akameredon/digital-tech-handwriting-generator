import math

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw

import model.teacher_ink as teacher_ink
from ingestion.calibration_sheet import (
    CELL_HEIGHT, CELL_WIDTH, DEFAULT_SAMPLE_ROWS, GRID_BOTTOM, GRID_COLUMNS,
    GRID_LEFT, GRID_RIGHT, GRID_ROWS, GRID_TOP, PAGE_HEIGHT, PAGE_WIDTH,
    extract_calibration_glyphs,
)
from model.teacher_ink import TeacherInkError, WORKSHEET_SOURCE, profile_from_confirmed_crops
from renderer.stroke_handwriting import HandwritingRenderer, WriterProfile


def crop(label, image, **changes):
    sample = {"label": label, "image": image, "label_source": WORKSHEET_SOURCE,
              "bbox": (7, 11, image.shape[1], image.shape[0]), "row": 1}
    sample.update(changes)
    return sample


def prepare(*samples, **kwargs):
    return profile_from_confirmed_crops(samples, name="synthetic", labels_confirmed=True, **kwargs)


def test_loop_preserves_cycle_every_edge_and_uniform_coordinates(monkeypatch):
    monkeypatch.delattr(cv2, "ximgproc", raising=False)
    image = np.zeros((100, 80), np.uint8)
    cv2.ellipse(image, (40, 50), (20, 32), 0, 0, 360, 255, 5)
    profile, report = prepare(crop("o", image))
    info = report["glyphs"]["o"]
    assert isinstance(profile, WriterProfile)
    assert profile.experimental and profile.incomplete
    assert report["experimental"] and report["incomplete"]
    assert report["available_labels"] == ["o"] and "z" in report["missing_labels"]
    assert info["component_count"] == 1
    assert info["skeleton_edges"] - info["skeleton_pixels"] + 1 == 1
    assert info["endpoint_pixels"] == 0 and info["junction_pixels"] == 0
    assert any("loop" in issue.lower() for issue in info["ambiguous_structure"])
    paths = profile.strokes["o"]
    assert all(2 <= len(path) <= teacher_ink.MAX_POINTS_PER_PATH for path in paths)
    assert paths[0][0] == paths[-1][-1]  # A closed cycle, even if chunked.
    assert all(paths[i][-1] == paths[i + 1][0] for i in range(len(paths) - 1))
    # Every traced edge is present exactly once and consists of neighboring pixels.
    scale = info["uniform_scale"]
    edges = []
    for path in paths:
        for a, b in zip(path, path[1:]):
            aa = tuple(round(v / scale) for v in a)
            bb = tuple(round(v / scale) for v in b)
            assert max(abs(aa[0] - bb[0]), abs(aa[1] - bb[1])) == 1
            edges.append(tuple(sorted((aa, bb))))
    assert len(edges) == len(set(edges)) == info["skeleton_edges"]


def test_two_loops_and_a_shared_junction_survive():
    image = np.zeros((100, 100), np.uint8)
    cv2.circle(image, (50, 32), 20, 255, 4)
    cv2.circle(image, (50, 72), 20, 255, 4)
    _, report = prepare(crop("8", image))
    info = report["glyphs"]["8"]
    assert info["component_count"] == 1
    assert info["hole_count"] == info["graph_cycle_rank"] == 2
    assert info["junction_pixels"] > 0
    assert any("pen order" in item for item in info["ambiguous_structure"])
    assert any("drawing direction" in item for item in info["ambiguous_structure"])


def test_topology_change_is_rejected_instead_of_silently_represented(monkeypatch):
    image = np.zeros((20, 20), np.uint8)
    cv2.rectangle(image, (3, 3), (16, 16), 255, 1)

    def erase_hole(ink, remaining_work):
        return np.ones_like(ink), ink.size

    monkeypatch.setattr(teacher_ink, "_thin", erase_hole)
    with pytest.raises(TeacherInkError, match="enclosed holes"):
        prepare(crop("o", image))


def test_branching_is_split_into_connected_paths_without_invented_bridges():
    image = np.zeros((90, 90), np.uint8)
    cv2.line(image, (45, 40), (45, 75), 255, 3)
    cv2.line(image, (45, 40), (15, 12), 255, 3)
    cv2.line(image, (45, 40), (75, 12), 255, 3)
    profile, report = prepare(crop("Y", image))
    info = report["glyphs"]["Y"]
    assert info["component_count"] == 1
    assert info["endpoint_pixels"] == 3
    assert info["junction_pixels"] >= 1
    assert any("Junctions" in issue for issue in info["ambiguous_structure"])
    assert len(profile.strokes["Y"]) >= 3
    x0, y0, _, _ = info["ink_bbox_in_crop"]
    for path in profile.strokes["Y"]:
        for x, y in path:
            px, py = round(x / info["uniform_scale"]), round(y / info["uniform_scale"])
            assert image[py, px] == 255


def test_disconnected_components_and_tiny_dots_survive_and_are_renderable():
    image = np.zeros((80, 50), np.uint8)
    cv2.line(image, (25, 38), (25, 70), 255, 3)
    image[12:14, 24:26] = 255  # A solid 2x2 island previously lost by thinning.
    image[5, 5] = 255
    profile, report = prepare(crop("i", image))
    info = report["glyphs"]["i"]
    assert info["component_count"] == 3
    assert info["restored_tiny_components"] == 1
    assert info["isolated_pixels"] == 2
    assert any("Disconnected" in issue for issue in info["ambiguous_structure"])
    assert any("Tiny components" in issue for issue in info["ambiguous_structure"])
    _, component_labels = cv2.connectedComponents(image, connectivity=8)
    x0, y0, _, _ = info["ink_bbox_in_crop"]
    for path in profile.strokes["i"]:
        belonging = {component_labels[round(y / info["uniform_scale"]),
                                      round(x / info["uniform_scale"])] for x, y in path}
        assert len(belonging) == 1 and 0 not in belonging
    dots = [path for path in profile.strokes["i"] if path[0] == path[-1]]
    assert len(dots) == 2 and all(len(dot) == 2 for dot in dots)
    # A zero-length, two-point path must be accepted by the existing renderer.
    canvas = Image.new("RGB", (30, 30), "white")
    renderer = HandwritingRenderer(profile, seed=0)
    renderer._draw_stroke(ImageDraw.Draw(canvas), [(15.0, 15.0), (15.0, 15.0)])
    assert canvas.getpixel((15, 15)) != (255, 255, 255)


def test_aspect_ratio_is_preserved_by_a_shared_full_crop_scale():
    image = np.zeros((30, 50), np.uint8)
    cv2.line(image, (5, 5), (35, 15), 255, 1)
    profile, report = prepare(crop("x", image))
    points = [point for path in profile.strokes["x"] for point in path]
    width = max(x for x, _ in points) - min(x for x, _ in points)
    height = max(y for _, y in points) - min(y for _, y in points)
    assert math.isclose(width, 30 / 49)
    assert math.isclose(height, 10 / 49)
    assert report["glyphs"]["x"]["uniform_scale"] == 1 / 49


def test_one_pixel_and_border_ink_are_valid():
    profile, report = prepare(crop(".", np.array([[255]], dtype=np.uint8)))
    assert profile.strokes["."] == [[(0.0, 0.0), (0.0, 0.0)]]
    assert report["glyphs"]["."]["component_count"] == 1
    assert any("bypasses" in limit for limit in report["renderer_constraints"])
    bordered = np.zeros((9, 9), np.uint8)
    bordered[:, 0] = 255
    p, r = prepare(crop("l", bordered))
    assert r["glyphs"]["l"]["ink_bbox_in_crop"] == [0, 0, 1, 9]
    assert all(x == 0 for path in p.strokes["l"] for x, _ in path)
    assert any("clipped" in issue for issue in r["glyphs"]["l"]["ambiguous_structure"])


def test_profile_round_trip_and_report_explains_marker_loss(tmp_path):
    image = np.zeros((5, 5), np.uint8)
    image[1:4, 2] = 255
    profile, report = prepare(crop("a", image))
    output = tmp_path / "sample.json"
    profile.save(output)
    loaded = WriterProfile.load(output)
    assert loaded.strokes == profile.strokes
    assert not hasattr(loaded, "experimental")
    assert any("discards experimental markers" in warning for warning in report["limitations"])
    assert any("baseline" in warning and "pressure" in warning for warning in report["limitations"])
    assert any("fallback" in warning for warning in report["renderer_constraints"])


@pytest.mark.parametrize("confirmation", [False, None, 1, "true", np.bool_(True)])
def test_requires_literal_explicit_confirmation(confirmation):
    with pytest.raises(TeacherInkError, match="confirmation"):
        profile_from_confirmed_crops([crop("a", np.ones((1, 1), np.uint8))],
                                     name="test", labels_confirmed=confirmation)


@pytest.mark.parametrize("source", [None, "verified", "natural_page", "guessed_position", "worksheet_cell"])
def test_unknown_or_unconfirmed_provenance_is_rejected(source):
    sample = crop("a", np.ones((1, 1), np.uint8), label_source=source)
    with pytest.raises(TeacherInkError, match="provenance"):
        prepare(sample)


@pytest.mark.parametrize("label", ["", "ab", " a", " ", "\n", 1, None, "\ud800"])
def test_exact_printable_single_character_labels(label):
    with pytest.raises(TeacherInkError, match="label"):
        prepare(crop(label, np.ones((1, 1), np.uint8)))


def test_duplicates_are_rejected_without_silent_overwrite():
    sample = crop("a", np.ones((1, 1), np.uint8))
    with pytest.raises(TeacherInkError, match="Duplicate"):
        prepare(sample, sample)


@pytest.mark.parametrize("image, message", [
    (np.zeros((4, 4), np.uint8), "blank"),
    (np.empty((0, 2), np.uint8), "empty"),
    (np.full((2, 2), np.nan), "nonfinite"),
    (np.array([[0, np.inf]]), "nonfinite"),
    (np.array([[0, 2]], dtype=np.uint8), "binary"),
    (np.array([[0, 1, 255]], dtype=np.uint8), "binary"),
    (np.array([[0, -1]], dtype=np.int16), "binary"),
    (np.zeros((257, 1), np.uint8), "size limit"),
    (np.zeros((1, 257), np.uint8), "size limit"),
    (np.array([[object()]], dtype=object), "invalid"),
])
def test_invalid_images_are_rejected(image, message):
    with pytest.raises(TeacherInkError, match=message):
        prepare(crop("a", image))


def test_invalid_shape_bbox_and_empty_inputs():
    with pytest.raises(TeacherInkError, match="two-dimensional"):
        prepare({"label": "a", "image": np.zeros((2, 2, 3)), "bbox": (0, 0, 2, 2), "label_source": WORKSHEET_SOURCE})
    image = np.ones((2, 3), np.uint8)
    for bbox in (None, (0, 0, 2, 2), (-1, 0, 3, 2), (0.0, 0, 3, 2), (True, 0, 3, 2)):
        with pytest.raises(TeacherInkError, match="bbox"):
            prepare(crop("a", image, bbox=bbox))
    with pytest.raises(TeacherInkError, match="At least one"):
        prepare()
    with pytest.raises(TeacherInkError, match="dictionary"):
        prepare("a")
    with pytest.raises(TeacherInkError, match="name"):
        profile_from_confirmed_crops([crop("a", image)], name=" ", labels_confirmed=True)


def test_work_and_complexity_limits_fail_closed(monkeypatch):
    image = np.zeros((40, 40), np.uint8)
    cv2.rectangle(image, (5, 5), (34, 34), 255, -1)
    monkeypatch.setattr(teacher_ink, "MAX_THINNING_PIXEL_ITERATIONS", 899)
    with pytest.raises(TeacherInkError, match="work limit"):
        prepare(crop("a", image))
    monkeypatch.setattr(teacher_ink, "MAX_THINNING_PIXEL_ITERATIONS", 40_000_000)
    monkeypatch.setattr(teacher_ink, "MAX_TOTAL_CROP_PIXELS", 100)
    with pytest.raises(TeacherInkError, match="total pixel"):
        prepare(crop("a", image))
    monkeypatch.setattr(teacher_ink, "MAX_TOTAL_CROP_PIXELS", 4_000_000)
    monkeypatch.setattr(teacher_ink, "MAX_SKELETON_PIXELS", 2)
    line = np.zeros((10, 10), np.uint8)
    line[1:9, 5] = 255
    with pytest.raises(TeacherInkError, match="pixel complexity"):
        prepare(crop("a", line))
    monkeypatch.setattr(teacher_ink, "MAX_SKELETON_PIXELS", 4_096)
    monkeypatch.setattr(teacher_ink, "MAX_SKELETON_EDGES", 2)
    with pytest.raises(TeacherInkError, match="edge complexity"):
        prepare(crop("a", line))
    monkeypatch.setattr(teacher_ink, "MAX_SKELETON_EDGES", 8_192)
    monkeypatch.setattr(teacher_ink, "MAX_POINTS_PER_GLYPH", 3)
    with pytest.raises(TeacherInkError, match="path complexity"):
        prepare(crop("a", line))
    monkeypatch.setattr(teacher_ink, "MAX_POINTS_PER_GLYPH", 4_096)
    monkeypatch.setattr(teacher_ink, "MAX_PATHS_PER_GLYPH", 1)
    dots = np.zeros((3, 3), np.uint8)
    dots[0, 0] = dots[2, 2] = 255
    with pytest.raises(TeacherInkError, match="path complexity"):
        prepare(crop("a", dots))


def test_total_count_and_total_point_budgets(monkeypatch):
    image = np.ones((1, 1), np.uint8)
    monkeypatch.setattr(teacher_ink, "MAX_CROPS", 1)
    with pytest.raises(TeacherInkError, match="Too many crops"):
        prepare(crop("a", image), crop("b", image))
    monkeypatch.setattr(teacher_ink, "MAX_CROPS", 128)
    monkeypatch.setattr(teacher_ink, "MAX_TOTAL_POINTS", 3)
    with pytest.raises(TeacherInkError, match="total trajectory point"):
        prepare(crop("a", image), crop("b", image))


def test_integration_with_actual_worksheet_extractor():
    # A synthetic worksheet: grid, corner codes, and eight arbitrary ink marks.
    width = 1600
    height = round(width * PAGE_HEIGHT / PAGE_WIDTH)
    image = np.full((height, width, 3), 255, np.uint8)
    px = lambda x: round(x / PAGE_WIDTH * width)
    py = lambda y: round((PAGE_HEIGHT - y) / PAGE_HEIGHT * height)
    for col in range(GRID_COLUMNS + 1):
        x = px(GRID_LEFT + col * CELL_WIDTH)
        cv2.line(image, (x, py(GRID_BOTTOM)), (x, py(GRID_TOP)), (185, 190, 200), 2)
    for row in range(GRID_ROWS + 1):
        y = py(GRID_TOP - row * CELL_HEIGHT)
        cv2.line(image, (px(GRID_LEFT), y), (px(GRID_RIGHT), y), (185, 190, 200), 2)
    centers = [(8 * 72 / 25.4, PAGE_HEIGHT - 8 * 72 / 25.4),
               (PAGE_WIDTH - 8 * 72 / 25.4, PAGE_HEIGHT - 8 * 72 / 25.4),
               (PAGE_WIDTH - 8 * 72 / 25.4, 8 * 72 / 25.4), (8 * 72 / 25.4, 8 * 72 / 25.4)]
    spacing = 2.6 * 72 / 25.4
    offsets = [[(0, 0)], [(-spacing / 2, 0), (spacing / 2, 0)],
               [(-spacing, 0), (0, 0), (spacing, 0)],
               [(-spacing / 2, -spacing / 2), (spacing / 2, -spacing / 2),
                (-spacing / 2, spacing / 2), (spacing / 2, spacing / 2)]]
    radius = max(2, round(0.8 * 72 / 25.4 / PAGE_WIDTH * width))
    for (cx, cy), group in zip(centers, offsets):
        for dx, dy in group:
            cv2.circle(image, (px(cx + dx), py(cy + dy)), radius, (15, 20, 30), -1)
    row_chars = DEFAULT_SAMPLE_ROWS[0]
    start = (GRID_COLUMNS - len(row_chars)) // 2
    for col in range(start, start + 8):
        left = GRID_LEFT + col * CELL_WIDTH
        x = px(left + CELL_WIDTH * 0.5)
        y0 = py(GRID_TOP - CELL_HEIGHT * 0.36)
        y1 = py(GRID_TOP - CELL_HEIGHT * 0.76)
        cv2.line(image, (x, y0), (x, y1), (20, 25, 30), 3)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    glyphs, missing = extract_calibration_glyphs(encoded.tobytes())
    assert len(glyphs) == 8 and len(missing) == len(teacher_ink.EXPECTED_LABELS) - 8
    profile, report = profile_from_confirmed_crops(glyphs, name="test", labels_confirmed=True)
    assert set(profile.strokes) == set(row_chars[:8])
    assert set(report["missing_labels"]) == set(missing)


def test_optional_experimental_renderer_uses_samples_and_requires_exact_coverage():
    renderer = pytest.importorskip("renderer.teacher_stroke_generation")
    image = np.zeros((20, 10), np.uint8)
    image[2, 5] = 255
    image[8:18, 5] = 255
    profile, _ = prepare(crop("i", image), crop(".", np.ones((1, 1), np.uint8)))
    options = renderer.RenderOptions(size_jitter=0, baseline_jitter=0)
    result = renderer.render_teacher_strokes("i.", profile, options=options)
    assert [placement.character for placement in result.placements] == ["i", "."]
    assert len(result.placements[0].strokes) == 2
    assert len(result.placements[1].strokes) == 1
    assert not result.joins
    with pytest.raises(renderer.UnsupportedTextError):
        renderer.render_teacher_strokes("X", profile, options=options)


def test_shared_crop_geometry_preserves_relative_size_and_vertical_position():
    # Same fixed cell dimensions, with deliberately different ink heights and
    # y positions. These are crop-relative observations, not baseline labels.
    big = np.zeros((40, 30), np.uint8)
    big[8:29, 10] = 255
    small = np.zeros((40, 30), np.uint8)
    small[20:27, 10] = 255
    dot = np.zeros((40, 30), np.uint8)
    dot[32, 10] = 255
    profile, report = prepare(crop("A", big), crop("a", small), crop(".", dot))
    extents = {}
    mins = {}
    for label, paths in profile.strokes.items():
        ys = [y for path in paths for _, y in path]
        extents[label] = max(ys) - min(ys)
        mins[label] = min(ys)
    assert extents["A"] > extents["a"] > extents["."]
    assert mins["A"] < mins["a"] < mins["."]
    assert all(info["coordinate_reference"] == "full_crop_origin"
               for info in report["glyphs"].values())
    assert any("asymmetric" in limitation and "baseline" in limitation
               for limitation in report["limitations"])
