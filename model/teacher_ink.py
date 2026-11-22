"""Experimental preparation of confirmed worksheet crops for the stroke renderer.

The paths describe the geometry of a static binary image, not pen trajectories.
Callers must explicitly confirm worksheet labels and keep the returned report with
any profile: the existing WriterProfile loader discards our experimental markers.
No label, writer identity, baseline, pressure or movement is inferred here.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from numbers import Integral
from typing import Any

import cv2
import numpy as np

from ingestion.preprocessor import DEFAULT_SAMPLE_ROWS
from renderer.stroke_handwriting import Stroke, WriterProfile


WORKSHEET_SOURCE = "worksheet_cell_teacher_confirmation_required"
EXPECTED_LABELS = "".join(DEFAULT_SAMPLE_ROWS)
MAX_CROPS = 128
MAX_CROP_SIDE = 256
MAX_CROP_PIXELS = 65_536
MAX_TOTAL_CROP_PIXELS = 4_000_000
MAX_THINNING_PIXEL_ITERATIONS = 40_000_000
MAX_SKELETON_PIXELS = 4_096
MAX_SKELETON_EDGES = 8_192
MAX_PATHS_PER_GLYPH = 128
MAX_POINTS_PER_PATH = 64
MAX_POINTS_PER_GLYPH = 4_096
MAX_TOTAL_POINTS = 100_000


class TeacherInkError(ValueError):
    """A crop, its confirmation, or its complexity is unsuitable for preparation."""


def _validated_crop(sample: Mapping[str, Any]) -> tuple[str, np.ndarray]:
    label = sample.get("label")
    if not isinstance(label, str) or len(label) != 1 or not label.isprintable() or label.isspace():
        raise TeacherInkError("Each label must be exactly one printable, non-space character.")
    source = sample.get("label_source")
    if not isinstance(source, str) or source != WORKSHEET_SOURCE:
        raise TeacherInkError(f"Unknown or untrusted label provenance for {label!r}.")
    image = sample.get("image")
    if not isinstance(image, np.ndarray) or image.ndim != 2:
        raise TeacherInkError(f"Crop for {label!r} must be a two-dimensional binary numpy array.")
    h, w = image.shape
    if not h or not w or h > MAX_CROP_SIDE or w > MAX_CROP_SIDE or h * w > MAX_CROP_PIXELS:
        raise TeacherInkError(f"Crop for {label!r} is empty or exceeds the size limit.")
    bbox = sample.get("bbox")
    if (not isinstance(bbox, (tuple, list)) or len(bbox) != 4
            or any(isinstance(v, (bool, np.bool_)) or not isinstance(v, Integral) for v in bbox)):
        raise TeacherInkError(f"Crop for {label!r} needs an integer worksheet bbox (x, y, width, height).")
    x, y, bw, bh = bbox
    if x < 0 or y < 0 or bw != w or bh != h:
        raise TeacherInkError(f"Crop for {label!r} has an invalid or mismatched worksheet bbox.")
    if image.dtype.kind not in "buif" or not np.isfinite(image).all():
        raise TeacherInkError(f"Crop for {label!r} contains invalid or nonfinite pixels.")
    # The ingestion contract is binary white foreground on black; never guess polarity
    # or threshold a natural-page image. Support both common binary encodings.
    white = (image == 1) | (image == 255)
    if not np.all((image == 0) | white) or (np.any(image == 1) and np.any(image == 255)):
        raise TeacherInkError(f"Crop for {label!r} must contain only binary white ink on black.")
    if not white.any():
        raise TeacherInkError(f"Crop for {label!r} is blank.")
    return label, white.astype(np.uint8)


def _thin(ink: np.ndarray, remaining_work: int) -> tuple[np.ndarray, int]:
    """Zhang-Suen thinning, with a zero border and a hard pixel-iteration budget.

    Both subiterations remove only topology-safe boundary pixels; this uses numpy
    rather than the optional, unavailable cv2.ximgproc extension.
    """
    padded = np.pad(ink, 1, mode="constant")
    work = 0
    while True:
        work += ink.size
        if work > remaining_work:
            raise TeacherInkError("Thinning exceeds the total pixel-iteration work limit.")
        changed = False
        for step in (0, 1):
            center = padded[1:-1, 1:-1]
            p2 = padded[:-2, 1:-1]
            p3 = padded[:-2, 2:]
            p4 = padded[1:-1, 2:]
            p5 = padded[2:, 2:]
            p6 = padded[2:, 1:-1]
            p7 = padded[2:, :-2]
            p8 = padded[1:-1, :-2]
            p9 = padded[:-2, :-2]
            ring = (p2, p3, p4, p5, p6, p7, p8, p9)
            neighbors = sum(ring)
            transitions = sum(((a == 0) & (b == 1)).astype(np.uint8)
                              for a, b in zip(ring, ring[1:] + ring[:1]))
            if step == 0:
                products_clear = (p2 * p4 * p6 == 0) & (p4 * p6 * p8 == 0)
            else:
                products_clear = (p2 * p4 * p8 == 0) & (p2 * p6 * p8 == 0)
            remove = ((center == 1) & (neighbors >= 2) & (neighbors <= 6)
                      & (transitions == 1) & products_clear)
            if np.any(remove):
                center[remove] = 0
                changed = True
        if not changed:
            return padded[1:-1, 1:-1].copy(), work


def _hole_count(ink: np.ndarray) -> int:
    """Count enclosed 4-connected background regions for 8-connected ink."""
    background = np.pad(1 - ink, 1, mode="constant", constant_values=1)
    # The count includes label zero and the single padded exterior region.
    return cv2.connectedComponents(background, connectivity=4)[0] - 2


def _paths(skeleton: np.ndarray, scale: float, origin: tuple[int, int] = (0, 0),
           axis_scale: tuple[float, float] = (1.0, 1.0)) -> tuple[list[Stroke], dict[str, int]]:
    """Trace each undirected skeleton edge once, splitting at junctions and ends.

    8-connected diagonal edges are retained only when neither orthogonal bridge
    exists, preventing artificial triangular shortcuts around digital corners.
    Cycles are closed explicitly. Isolated pixels become zero-length two-point
    paths, which the current renderer can draw as dots.
    """
    locations = np.argwhere(skeleton)
    if len(locations) == 0:
        raise TeacherInkError("Thinning lost all foreground pixels.")
    if len(locations) > MAX_SKELETON_PIXELS:
        raise TeacherInkError("Skeleton exceeds the pixel complexity limit.")
    nodes = {tuple(map(int, loc)) for loc in locations}
    graph: dict[tuple[int, int], list[tuple[int, int]]] = {node: [] for node in nodes}
    edge_count = 0
    for y, x in sorted(nodes):
        for dy, dx in ((0, 1), (1, -1), (1, 0), (1, 1)):
            other = (y + dy, x + dx)
            if other not in nodes:
                continue
            if dy and dx and ((y, x + dx) in nodes or (y + dy, x) in nodes):
                continue
            graph[(y, x)].append(other)
            graph[other].append((y, x))
            edge_count += 1
            if edge_count > MAX_SKELETON_EDGES:
                raise TeacherInkError("Skeleton exceeds the edge complexity limit.")
    for neighbors in graph.values():
        neighbors.sort()

    used: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    paths: list[Stroke] = []
    point_count = 0

    def edge(a: tuple[int, int], b: tuple[int, int]):
        return (a, b) if a < b else (b, a)

    def save_path(points: list[tuple[int, int]]) -> None:
        nonlocal point_count
        if len(points) == 1:
            points = points * 2
        # Bound renderer resampling costs without dropping edges: adjacent chunks
        # share exactly their boundary point and never bridge separate paths.
        for start in range(0, len(points) - 1, MAX_POINTS_PER_PATH - 1):
            chunk = points[start:start + MAX_POINTS_PER_PATH]
            point_count += len(chunk)
            if len(paths) >= MAX_PATHS_PER_GLYPH or point_count > MAX_POINTS_PER_GLYPH:
                raise TeacherInkError("Skeleton exceeds the path complexity limit.")
            paths.append([(float((x + origin[0]) * scale * axis_scale[0]),
                           float((y + origin[1]) * scale * axis_scale[1])) for y, x in chunk])

    def trace(start: tuple[int, int], neighbor: tuple[int, int]) -> list[tuple[int, int]]:
        path = [start, neighbor]
        used.add(edge(start, neighbor))
        previous, current = start, neighbor
        while len(graph[current]) == 2:
            next_node = graph[current][0] if graph[current][1] == previous else graph[current][1]
            key = edge(current, next_node)
            if key in used:
                break
            used.add(key)
            path.append(next_node)
            previous, current = current, next_node
        return path

    # Start at every endpoint and junction, then handle remaining closed cycles.
    for node in sorted(nodes):
        if not graph[node]:
            save_path([node])
        elif len(graph[node]) != 2:
            for neighbor in graph[node]:
                if edge(node, neighbor) not in used:
                    save_path(trace(node, neighbor))
    for node in sorted(nodes):
        for neighbor in graph[node]:
            if edge(node, neighbor) not in used:
                save_path(trace(node, neighbor))
    if len(used) != edge_count:
        raise TeacherInkError("Could not trace every skeleton edge safely.")
    return paths, {
        "skeleton_pixels": len(nodes),
        "skeleton_edges": edge_count,
        "endpoint_pixels": sum(len(n) == 1 for n in graph.values()),
        "junction_pixels": sum(len(n) > 2 for n in graph.values()),
        "isolated_pixels": sum(not n for n in graph.values()),
        "path_count": len(paths),
        "point_count": point_count,
    }


def profile_from_confirmed_crops(
    glyphs: Iterable[Mapping[str, Any]], *, name: str, labels_confirmed: bool
) -> tuple[WriterProfile, dict[str, Any]]:
    """Prepare an experimental profile and a report from confirmed sheet crops.

    Each crop is the ingestion dictionary with ``label``, ``image``, ``bbox``,
    and the exact worksheet ``label_source``; extra ingestion keys are accepted.
    ``labels_confirmed`` must be the literal True. This is a caller assertion,
    not a cryptographic verification of provenance or confirmation. Reject the
    entire batch on any invalid crop, duplicate label, or resource limit.

    Coordinates use the full crop origin mapped into a common crop-sized
    reference (the first sample sets reference dimensions), with one shared scale.
    Raster-rounding size differences are normalized per axis. Vertical placement
    remains worksheet-relative, not a measured baseline. Multiple paths represent skeleton edges,
    not recovered pen movements. Keep the returned report with the profile.
    """
    if labels_confirmed is not True:
        raise TeacherInkError("Explicit label confirmation (labels_confirmed=True) is required.")
    if not isinstance(name, str) or not name.strip() or len(name) > 120 or not name.isprintable():
        raise TeacherInkError("A printable, nonempty profile name of at most 120 characters is required.")
    try:
        iterator = iter(glyphs)
    except TypeError as exc:
        raise TeacherInkError("Glyphs must be an iterable of worksheet crop dictionaries.") from exc
    strokes: dict[str, list[Stroke]] = {}
    crop_size: tuple[int, int] | None = None
    details: dict[str, dict[str, Any]] = {}
    total_crop_pixels = total_work = total_points = 0
    for index, sample in enumerate(iterator):
        if index >= MAX_CROPS:
            raise TeacherInkError("Too many crops in one batch.")
        if not isinstance(sample, Mapping):
            raise TeacherInkError("Each crop must be a worksheet crop dictionary.")
        label, ink = _validated_crop(sample)
        current_size = (ink.shape[1], ink.shape[0])
        if crop_size is None:
            crop_size = current_size
        if label in strokes:
            raise TeacherInkError(f"Duplicate label {label!r}; samples cannot overwrite one another.")
        total_crop_pixels += ink.size
        if total_crop_pixels > MAX_TOTAL_CROP_PIXELS:
            raise TeacherInkError("Crops exceed the total pixel limit.")
        ys, xs = np.nonzero(ink)
        x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
        bounded_ink = ink[y0:y1 + 1, x0:x1 + 1]
        count, component_labels, stats, _ = cv2.connectedComponentsWithStats(bounded_ink, connectivity=8)
        components = count - 1
        skeleton, work = _thin(bounded_ink, MAX_THINNING_PIXEL_ITERATIONS - total_work)
        total_work += work
        # Simultaneous deletion can erase a solid 2x2 island. Restore one of its
        # original pixels as a dot; do not make this approximation for bigger
        # components, whose lost geometry might include significant structure.
        retained = np.bincount(component_labels[skeleton != 0], minlength=count)
        restored = 0
        for component in np.flatnonzero(retained[1:] == 0) + 1:
            sx, sy, sw, sh, area = (int(v) for v in stats[component])
            if sw > 2 or sh > 2 or area > 4:
                raise TeacherInkError(f"Thinning lost a nontrivial component for {label!r}.")
            candidates = np.argwhere(component_labels[sy:sy + sh, sx:sx + sw] == component)
            py, px = (int(v) for v in candidates[0])
            skeleton[sy + py, sx + px] = 1
            restored += 1
        skeleton_components = cv2.connectedComponents(skeleton, connectivity=8)[0] - 1
        if components != skeleton_components:
            raise TeacherInkError(f"Thinning changed the connected component count for {label!r}.")
        holes = _hole_count(bounded_ink)
        if _hole_count(skeleton) != holes:
            raise TeacherInkError(f"Thinning changed the number of enclosed holes for {label!r}.")
        # One em scale from the common full-crop geometry; retain the crop origin
        # so ink size and vertical position remain comparable across cells. This
        # is worksheet-relative placement, not evidence of a true writing baseline.
        reference_width, reference_height = crop_size
        scale = 1.0 / max(reference_width - 1, reference_height - 1, 1)
        axis_scale = (
            (reference_width - 1) / max(ink.shape[1] - 1, 1),
            (reference_height - 1) / max(ink.shape[0] - 1, 1),
        )
        paths, info = _paths(skeleton, scale, (x0, y0), axis_scale)
        total_points += info["point_count"]
        if total_points > MAX_TOTAL_POINTS:
            raise TeacherInkError("Crops exceed the total trajectory point limit.")
        ambiguous = []
        if components > 1:
            ambiguous.append("Disconnected marks remain separate; their semantic relationship and pen lifts are unknown.")
        if info["junction_pixels"]:
            ambiguous.append("Junctions or touching strokes are ambiguous; crossings and pen order are unknown.")
        cycle_rank = info["skeleton_edges"] - info["skeleton_pixels"] + components
        if holes:
            ambiguous.append("Closed loops have no known starting point or drawing direction.")
        if cycle_rank != holes:
            ambiguous.append("The pixel graph has ambiguous cycles not matching the image holes; review its structure.")
        if x0 == 0 or y0 == 0 or x1 == ink.shape[1] - 1 or y1 == ink.shape[0] - 1:
            ambiguous.append("Ink touches the crop boundary and may be clipped.")
        if restored:
            ambiguous.append("Tiny components erased by thinning were retained as single-pixel dots.")
        info.update({
            "component_count": components,
            "hole_count": holes,
            "graph_cycle_rank": cycle_rank,
            "restored_tiny_components": restored,
            "ink_bbox_in_crop": [x0, y0, x1 - x0 + 1, y1 - y0 + 1],
            "uniform_scale": scale,
            "coordinate_reference": "full_crop_origin",
            "crop_size": [int(ink.shape[1]), int(ink.shape[0])],
            "reference_crop_size": list(crop_size),
            "ambiguous_structure": ambiguous,
        })
        strokes[label] = paths
        details[label] = info
    if not strokes:
        raise TeacherInkError("At least one confirmed crop is required.")
    missing = [label for label in EXPECTED_LABELS if label not in strokes]
    # Neutralize optional effects; the renderer still has built-in jitter, fixed
    # width and layout behavior. These defaults are not inferred from the sample.
    profile = WriterProfile(name=name, strokes=strokes, slant=0.0, baseline_jitter=0.0,
                            size_jitter=0.0, pressure=0.0, connect=0.0)
    # The existing save method writes these flags, but WriterProfile.load filters
    # unknown fields. The report is the authoritative, separately retained marker.
    profile.experimental = True
    profile.incomplete = True
    report: dict[str, Any] = {
        "experimental": True,
        "incomplete": True,
        "available_labels": sorted(strokes),
        "missing_labels": missing,
        "coverage_complete": not missing,
        "glyphs": details,
        "limitations": [
            "Coordinates preserve common fixed-crop scale and crop-relative vertical placement; the worksheet crop padding is asymmetric and supplies no genuine baseline evidence. Do not interpret these coordinates as baseline-aligned metrics.",
            "Caller-provided confirmation and provenance are assertions, not independently verified proof.",
            "Static crops cannot recover baseline, real motion, pen order or direction, pen lifts, pressure, or writer identity.",
            "Paths are skeleton geometry, not authentic or production-quality handwriting; thin/noisy or touching ink may be ambiguous.",
            "Disconnected components are separate paths, but their intended relationships are unsupported and require review.",
            "The existing WriterProfile.load discards experimental markers; retain this report with the profile.",
        ],
        "renderer_constraints": [
            "Legacy HandwritingRenderer uses built-in fallbacks for missing glyphs and may substitute lowercase samples for uppercase.",
            "Legacy HandwritingRenderer bypasses sampled strokes for , . ; : ! ? and spaces, and uses fixed advances and additional random skew.",
            "Legacy HandwritingRenderer resamples paths, uses a fixed synthetic stroke width, and does not reproduce the original raster or baseline.",
            "The experimental sample-backed renderer requires exact character coverage and has its own resource and layout limits.",
        ],
    }
    return profile, report
