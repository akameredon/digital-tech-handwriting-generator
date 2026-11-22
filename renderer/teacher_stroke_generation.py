"""Experimental, bounded rendering from explicitly supplied writer trajectories.

This is an engineering prototype, not machine learning or evidence that a
particular teacher authored the paths. The caller is responsible for obtaining
and verifying suitable, consensually supplied teacher-specific samples.
Only ``WriterProfile.strokes`` and ``WriterProfile.ink`` are used; other legacy
profile style fields are deliberately ignored. No font or built-in glyph is
used, and ``WriterProfile.glyph`` is never called.

Coordinates in a profile are finite normalized (x, y) points in [-2, 2].
Each glyph is an ordered, nonempty sequence of nonempty pen-down strokes. A
single point (or repeated identical points) is a legitimate dot stroke. Paths
are rendered as polylines with round dots at their supplied points; they are
not learned handwriting. Joins are disabled by default. If explicitly enabled,
a probabilistic heuristic joins actual endpoints of adjacent single-stroke,
non-dot alphabetic glyphs with a straight line. Such joins are synthetic, not
writer-supplied evidence. Static scanned ink cannot establish true pen order.

Only ASCII space, tab and LF are layout whitespace. Other whitespace and
controls are reported as unsupported, with Python string/code-point offsets.
A space/tab that causes a wrap is consumed as a line separator. Long words are
wrapped between characters. Rendering either succeeds completely or raises
before allocating any image; it never returns partial pages.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

from PIL import Image, ImageDraw

from renderer.stroke_handwriting import WriterProfile

Point = Tuple[float, float]
Stroke = Tuple[Point, ...]
Glyph = Tuple[Stroke, ...]

# Hard ceilings cannot be raised through options.
_MAX_PROFILE_GLYPHS = 4096
_MAX_PROFILE_STROKES_PER_GLYPH = 128
_MAX_PROFILE_POINTS_PER_GLYPH = 4096
_MAX_PROFILE_POINTS = 100_000
_MAX_RENDER_POINTS = 500_000
_MAX_INPUT_CHARACTERS = 20_000
_MAX_PAGE_PIXELS = 4_194_304
_MAX_TOTAL_PIXELS = 33_554_432
_MAX_PAGES = 64
_LAYOUT = frozenset((' ', '\t', '\n'))


class InvalidProfileError(ValueError):
    """The explicit profile is absent or malformed."""


class LayoutError(ValueError):
    """A complete rendering cannot fit within the requested resource bounds."""


@dataclass(frozen=True)
class UnsupportedCharacter:
    character: str
    offsets: Tuple[int, ...]
    reason: str  # missing_trajectory or unsupported_whitespace_or_control


class UnsupportedTextError(ValueError):
    """Text preflight failed; ``unsupported`` groups exact characters/offsets."""

    def __init__(self, unsupported: Tuple[UnsupportedCharacter, ...]):
        self.unsupported = unsupported
        details = ', '.join(f'{item.character!r} at {item.offsets} ({item.reason})'
                            for item in unsupported)
        super().__init__(f'Unsupported text: {details}')


@dataclass(frozen=True)
class RenderOptions:
    page_width: int = 800
    page_height: int = 1000
    margin: int = 32
    line_height: int = 64
    em_size: float = 40.0
    letter_spacing: float = 5.0
    space_advance: float = 18.0
    stroke_width: int = 2
    size_jitter: float = 0.04
    baseline_jitter: float = 1.5
    enable_heuristic_joins: bool = False
    join_probability: float = 0.75
    join_max_distance: float = 32.0
    max_pages: int = 32
    max_characters: int = 10_000
    background: Tuple[int, int, int] = (255, 255, 255)


@dataclass(frozen=True)
class CharacterPlacement:
    offset: int
    character: str
    page_index: int
    line_index: int  # zero-based within page
    # All transformed supplied strokes, in their original order, including dots.
    strokes: Glyph
    # Conservative ink bounds (left, top, right, bottom), in page coordinates.
    bounds: Tuple[float, float, float, float]


@dataclass(frozen=True)
class JoinPlacement:
    page_index: int
    line_index: int
    from_offset: int
    to_offset: int
    start: Point
    end: Point


@dataclass(frozen=True)
class RenderResult:
    pages: List[Image.Image]
    placements: Tuple[CharacterPlacement, ...]
    joins: Tuple[JoinPlacement, ...]
    # Inclusive integer drawable pixel limits, same for every page.
    drawable_bounds: Tuple[int, int, int, int]
    warnings: Tuple[str, ...]


def _number(value: object, name: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{name} must be a finite number in [{low}, {high}]')
    try:
        number = float(value)
    except (OverflowError, ValueError):
        raise ValueError(f'{name} must be a finite number in [{low}, {high}]') from None
    if not math.isfinite(number) or not low <= number <= high:
        raise ValueError(f'{name} must be a finite number in [{low}, {high}]')
    return number


def _integer(value: object, name: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f'{name} must be an integer in [{low}, {high}]')
    return value


def _color(value: object, name: str) -> Tuple[int, int, int]:
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        raise ValueError(f'{name} must be three integer RGB channels')
    return tuple(_integer(c, name, 0, 255) for c in value)  # type: ignore[return-value]


def _non_dot(stroke: Stroke) -> bool:
    """Reject point marks and very small strokes as possible detached dots."""
    xs = [p[0] for p in stroke]
    ys = [p[1] for p in stroke]
    return math.hypot(max(xs) - min(xs), max(ys) - min(ys)) >= 0.08


def _profile_snapshot(profile: WriterProfile) -> Tuple[Dict[str, Glyph], Tuple[int, int, int]]:
    if not isinstance(profile, WriterProfile):
        raise InvalidProfileError('an explicit WriterProfile is required')
    if not isinstance(profile.strokes, dict) or not profile.strokes:
        raise InvalidProfileError('profile.strokes must be a nonempty character-to-strokes dictionary')
    if len(profile.strokes) > _MAX_PROFILE_GLYPHS:
        raise InvalidProfileError('too many profile glyphs')
    try:
        ink = _color(profile.ink, 'profile.ink')
    except ValueError as exc:
        raise InvalidProfileError(str(exc)) from exc
    result: Dict[str, Glyph] = {}
    total_points = 0
    for ch, raw_strokes in profile.strokes.items():
        if not isinstance(ch, str) or len(ch) != 1 or ch.isspace() or not ch.isprintable():
            raise InvalidProfileError(f'profile key {ch!r} must be one printable, non-whitespace character')
        if not isinstance(raw_strokes, (list, tuple)) or not raw_strokes:
            raise InvalidProfileError(f'{ch!r} must have nonempty strokes')
        if len(raw_strokes) > _MAX_PROFILE_STROKES_PER_GLYPH:
            raise InvalidProfileError(f'{ch!r} has too many strokes')
        strokes: List[Stroke] = []
        glyph_points = 0
        for raw_stroke in raw_strokes:
            if not isinstance(raw_stroke, (list, tuple)) or not raw_stroke:
                raise InvalidProfileError(f'{ch!r} contains an empty or invalid stroke')
            glyph_points += len(raw_stroke)
            total_points += len(raw_stroke)
            if glyph_points > _MAX_PROFILE_POINTS_PER_GLYPH or total_points > _MAX_PROFILE_POINTS:
                raise InvalidProfileError('profile contains too many trajectory points')
            points: List[Point] = []
            for point in raw_stroke:
                if not isinstance(point, (tuple, list)) or len(point) != 2:
                    raise InvalidProfileError(f'{ch!r} has a malformed point')
                try:
                    points.append((_number(point[0], 'x', -2, 2), _number(point[1], 'y', -2, 2)))
                except ValueError as exc:
                    raise InvalidProfileError(f'{ch!r}: {exc}') from exc
            strokes.append(tuple(points))
        result[ch] = tuple(strokes)
    return result, ink


def _validate_options(o: RenderOptions) -> Tuple[int, int, int, int]:
    if not isinstance(o, RenderOptions):
        raise ValueError('options must be RenderOptions')
    w = _integer(o.page_width, 'page_width', 32, 4096)
    h = _integer(o.page_height, 'page_height', 32, 4096)
    m = _integer(o.margin, 'margin', 0, 2047)
    line_height = _integer(o.line_height, 'line_height', 1, 4096)
    _integer(o.stroke_width, 'stroke_width', 1, 32)
    _integer(o.max_pages, 'max_pages', 1, _MAX_PAGES)
    _integer(o.max_characters, 'max_characters', 0, _MAX_INPUT_CHARACTERS)
    _number(o.em_size, 'em_size', 1, 512)
    _number(o.letter_spacing, 'letter_spacing', 0, 256)
    _number(o.space_advance, 'space_advance', 1, 512)
    _number(o.size_jitter, 'size_jitter', 0, 0.25)
    _number(o.baseline_jitter, 'baseline_jitter', 0, 64)
    if not isinstance(o.enable_heuristic_joins, bool):
        raise ValueError('enable_heuristic_joins must be a boolean')
    _number(o.join_probability, 'join_probability', 0, 1)
    _number(o.join_max_distance, 'join_max_distance', 0, 512)
    _color(o.background, 'background')
    if w * h > _MAX_PAGE_PIXELS:
        raise ValueError('page pixel limit exceeded')
    if w - 2 * m <= 0 or h - 2 * m < line_height:
        raise ValueError('margins and line_height leave no usable line')
    pad = math.ceil(o.stroke_width / 2) + 1
    if w - 2 * m - 1 - 2 * pad < 0:
        raise ValueError('drawable width is too small for stroke width')
    return (m, m, w - m - 1, h - m - 1)


class TeacherStrokeGenerator:
    """Snapshot a supplied profile; call render repeatedly for reproducible pages."""

    def __init__(self, profile: WriterProfile, options: RenderOptions | None = None):
        self._glyphs, self._ink = _profile_snapshot(profile)
        self.options = options if options is not None else RenderOptions()
        self._drawable_bounds = _validate_options(self.options)

    def render(self, text: str, *, seed: int = 0) -> RenderResult:
        if not isinstance(text, str):
            raise TypeError('text must be a string')
        _integer(seed, 'seed', -(2**63), 2**63 - 1)
        o = self.options
        # Revalidate, including options that a caller may have replaced on the object.
        drawable = _validate_options(o)
        if tuple(o.background) == self._ink:
            raise ValueError('profile ink must differ from the background')
        if len(text) > o.max_characters:
            raise LayoutError('text exceeds max_characters')

        unsupported: Dict[str, Tuple[str, List[int]]] = {}
        point_count = 0
        used = set()
        for offset, ch in enumerate(text):
            if ch in _LAYOUT:
                continue
            if ch.isspace() or not ch.isprintable():
                reason = 'unsupported_whitespace_or_control'
            elif ch not in self._glyphs:
                reason = 'missing_trajectory'
            else:
                used.add(ch)
                point_count += sum(len(s) for s in self._glyphs[ch])
                continue
            if ch not in unsupported:
                unsupported[ch] = (reason, [])
            unsupported[ch][1].append(offset)
        if unsupported:
            raise UnsupportedTextError(tuple(UnsupportedCharacter(ch, tuple(offsets), reason)
                                             for ch, (reason, offsets) in unsupported.items()))
        if point_count > _MAX_RENDER_POINTS:
            raise LayoutError('transformed trajectory point budget exceeded')

        # Shared y reference preserves the source profile's vertical alignment.
        ys = [y for ch in used for stroke in self._glyphs[ch] for _, y in stroke]
        min_y = min(ys, default=0.0)
        max_y = max(ys, default=0.0)
        pad = math.ceil(o.stroke_width / 2) + 1
        max_size = o.em_size * (1 + o.size_jitter)
        needed_height = 2 * pad + 1 + 2 * o.baseline_jitter + (max_y - min_y) * max_size
        if needed_height > o.line_height:
            raise LayoutError('line_height is too small for the supplied trajectory bounds and variation')

        left = float(o.margin + pad)
        right = float(o.page_width - o.margin - 1 - pad)
        width = right - left
        rows_per_page = (o.page_height - 2 * o.margin) // o.line_height
        rng = random.Random(seed)
        placements: List[CharacterPlacement] = []
        joins: List[JoinPlacement] = []
        page, line, x = 0, 0, left
        previous: CharacterPlacement | None = None

        def next_line() -> None:
            nonlocal page, line, x, previous
            line += 1
            if line >= rows_per_page:
                page += 1
                line = 0
                if page >= o.max_pages or (page + 1) * o.page_width * o.page_height > _MAX_TOTAL_PIXELS:
                    raise LayoutError('page count or total pixel budget exceeded')
            x = left
            previous = None

        for offset, ch in enumerate(text):
            if ch == '\n':
                next_line()
                continue
            if ch in (' ', '\t'):
                advance = o.space_advance * (4 if ch == '\t' else 1)
                if advance > width:
                    raise LayoutError(f'whitespace at offset {offset} is wider than the drawable line')
                if x + advance > right:
                    next_line()  # Boundary whitespace becomes the line break.
                else:
                    x += advance
                    previous = None
                continue

            glyph = self._glyphs[ch]
            # At a word boundary, reserve enough nominal space for the complete
            # word before placing its first glyph. If the word fits on a fresh
            # line, move it intact rather than splitting merely because its first
            # character fits in the remainder. Actual glyph sizes/jitter and x
            # advances below remain unchanged and are still bounds-checked.
            if offset == 0 or text[offset - 1] in (' ', '\t', '\n'):
                end = offset
                word_width = 0.0
                while end < len(text) and text[end] not in (' ', '\t', '\n'):
                    word_glyph = self._glyphs[text[end]]
                    word_xs = [px for stroke in word_glyph for px, _ in stroke]
                    glyph_advance = max((max(word_xs) - min(word_xs)) * max_size,
                                        float(o.stroke_width))
                    word_width += glyph_advance
                    if end > offset:
                        word_width += o.letter_spacing
                    end += 1
                if end - offset > 1:
                    word_width -= o.letter_spacing  # No spacing after the word's last glyph.
                if word_width <= width and x + word_width > right:
                    next_line()
            min_x = min(px for s in glyph for px, _ in s)
            max_x = max(px for s in glyph for px, _ in s)
            size = o.em_size * (1 + rng.uniform(-o.size_jitter, o.size_jitter))
            glyph_width = (max_x - min_x) * size
            if glyph_width > width:
                raise LayoutError(f'glyph {ch!r} at offset {offset} is wider than the drawable line')
            if x + glyph_width > right:
                next_line()
            y_base = (o.margin + line * o.line_height + pad + o.baseline_jitter
                      + rng.uniform(-o.baseline_jitter, o.baseline_jitter))
            transformed: Glyph = tuple(tuple((x + (px - min_x) * size,
                                               y_base + (py - min_y) * size)
                                              for px, py in stroke) for stroke in glyph)
            xs = [p[0] for s in transformed for p in s]
            y_values = [p[1] for s in transformed for p in s]
            bounds = (min(xs) - pad, min(y_values) - pad, max(xs) + pad, max(y_values) + pad)
            placement = CharacterPlacement(offset, ch, page, line, transformed, bounds)
            # Multi-stroke glyphs may have detached dots or marks. Conservatively
            # never join them; also reject tiny/dot-only single-stroke glyphs.
            if (o.enable_heuristic_joins and previous is not None
                    and previous.offset + 1 == offset
                    and previous.character.isalpha() and ch.isalpha()
                    and len(previous.strokes) == 1 and len(transformed) == 1
                    and _non_dot(self._glyphs[previous.character][0])
                    and _non_dot(glyph[0])):
                start, end = previous.strokes[-1][-1], transformed[0][0]
                if (math.dist(start, end) <= o.join_max_distance
                        and rng.random() < o.join_probability):
                    joins.append(JoinPlacement(page, line, previous.offset, offset, start, end))
            placements.append(placement)
            previous = placement
            x += max(glyph_width, float(o.stroke_width)) + o.letter_spacing

        # All validation and pagination precedes the first allocation of a page.
        pages = [Image.new('RGB', (o.page_width, o.page_height), tuple(o.background))
                 for _ in range(page + 1)]
        draws = [ImageDraw.Draw(image) for image in pages]

        def draw_stroke(draw: ImageDraw.ImageDraw, points: Stroke) -> None:
            if len(points) > 1:
                draw.line(points, fill=self._ink, width=o.stroke_width, joint='curve')
            radius = o.stroke_width / 2
            for px, py in points:
                draw.ellipse((px - radius, py - radius, px + radius, py + radius), fill=self._ink)

        # Draw joins first so every supplied pen stroke remains on top.
        for join in joins:
            draw_stroke(draws[join.page_index], (join.start, join.end))
        for item in placements:
            for stroke in item.strokes:
                draw_stroke(draws[item.page_index], stroke)
        warnings = (('Experimental joins are synthetic endpoint heuristics, not supplied teacher trajectories.',)
                    if o.enable_heuristic_joins else ())
        return RenderResult(pages, tuple(placements), tuple(joins), drawable, warnings)


def render_teacher_strokes(text: str, profile: WriterProfile, *,
                           options: RenderOptions | None = None, seed: int = 0) -> RenderResult:
    """Convenience wrapper around :class:`TeacherStrokeGenerator`."""
    return TeacherStrokeGenerator(profile, options).render(text, seed=seed)
