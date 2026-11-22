"""Tests for the strict, experimental teacher trajectory prototype."""
from dataclasses import replace

import pytest
from PIL import Image

from renderer.stroke_handwriting import WriterProfile
from renderer.teacher_stroke_generation import (
    InvalidProfileError,
    LayoutError,
    RenderOptions,
    TeacherStrokeGenerator,
    UnsupportedTextError,
    render_teacher_strokes,
)


@pytest.fixture
def profile():
    # These are synthetic test paths, not samples of an actual teacher.
    return WriterProfile(ink=(0, 0, 0), strokes={
        'a': [[(0.0, 0.1), (0.35, 0.8), (0.7, 0.1)]],
        'b': [[(0.0, 0.1), (0.0, 0.8), (0.65, 0.8)]],
        'i': [[(0.2, 0.4), (0.2, 0.9)], [(0.2, 0.1)]],
        'j': [[(0.2, 0.1)]],
        'A': [[(0.0, 0.9), (0.4, 0.0), (0.8, 0.9)], [(0.2, 0.6), (0.6, 0.6)]],
        '.': [[(0.2, 0.9)]],
        ',': [[(0.2, 0.8), (0.1, 1.0)]],
        '!': [[(0.2, 0.0), (0.2, 0.65)], [(0.2, 0.9)]],
    })


def opts(**overrides):
    return replace(RenderOptions(page_width=140, page_height=100, margin=5,
                                 line_height=36, em_size=20, stroke_width=2,
                                 letter_spacing=4, space_advance=10,
                                 size_jitter=0, baseline_jitter=0), **overrides)


def test_strict_exact_case_punctuation_digits_unknown_and_controls_preflight(profile, monkeypatch):
    profile.strokes.pop('A')
    profile.strokes.pop(',')
    profile.strokes.pop('!')
    # A missing capital must not use lowercase; punctuation and digits do not
    # use the legacy generic paths. Controls/whitespace are not silently lost.
    text = 'aA.,! 1\x00\u00a0\t\n\r\u200bA'
    generator = TeacherStrokeGenerator(profile, opts())
    monkeypatch.setattr(Image, 'new', lambda *a, **k: pytest.fail('allocated before preflight'))
    with pytest.raises(UnsupportedTextError) as caught:
        generator.render(text)
    found = {u.character: (u.offsets, u.reason) for u in caught.value.unsupported}
    assert found == {
        'A': ((1, 13), 'missing_trajectory'),
        ',': ((3,), 'missing_trajectory'),
        '!': ((4,), 'missing_trajectory'),
        '1': ((6,), 'missing_trajectory'),
        '\x00': ((7,), 'unsupported_whitespace_or_control'),
        '\u00a0': ((8,), 'unsupported_whitespace_or_control'),
        '\r': ((11,), 'unsupported_whitespace_or_control'),
        '\u200b': ((12,), 'unsupported_whitespace_or_control'),
    }


def test_no_glyph_method_or_generic_paths_are_used(profile, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('WriterProfile.glyph fallback was used')
    monkeypatch.setattr(WriterProfile, 'glyph', forbidden)
    result = render_teacher_strokes('Aa.,!', profile, options=opts())
    assert [p.character for p in result.placements] == list('Aa.,!')
    for unknown in ('z', 'Z', '?', '0', '💡'):
        with pytest.raises(UnsupportedTextError) as caught:
            render_teacher_strokes(unknown, profile, options=opts())
        assert caught.value.unsupported[0].character == unknown
        assert caught.value.unsupported[0].offsets == (0,)


def test_uppercase_only_profile_never_supplies_a_lowercase_fallback():
    p = WriterProfile(strokes={'A': [[(0, 0), (1, 1)]]})
    with pytest.raises(UnsupportedTextError) as caught:
        render_teacher_strokes('a', p, options=opts())
    assert caught.value.unsupported[0].character == 'a'
    assert caught.value.unsupported[0].reason == 'missing_trajectory'


def test_explicit_unicode_glyphs_and_code_point_offsets(profile):
    profile.strokes['🖉'] = [[(0, 0), (0.3, 0.8)]]
    text = '🖉a\n🖉.'
    result = render_teacher_strokes(text, profile, options=opts())
    assert [(p.offset, p.character) for p in result.placements] == [
        (0, '🖉'), (1, 'a'), (3, '🖉'), (4, '.')]


@pytest.mark.parametrize('strokes', [
    {}, {'ab': [[(0, 0)]]}, {' ': [[(0, 0)]]}, {'\n': [[(0, 0)]]},
    {'a': []}, {'a': [[]]}, {'a': [[(0,)]]}, {'a': [[(0, 0, 0)]]},
    {'a': [[(float('nan'), 0)]]}, {'a': [[(0, float('inf'))]]},
    {'a': [[(2.01, 0)]]}, {'a': [[(0, -2.01)]]},
    {'a': [[(True, 0)]]}, {'a': 'not strokes'},
    {'a': [[(0, 0)]] * 129}, {'a': [[(0, 0)] * 4097]},
])
def test_invalid_profiles_are_rejected(strokes):
    with pytest.raises(InvalidProfileError):
        TeacherStrokeGenerator(WriterProfile(strokes=strokes))


def test_profile_required_and_ink_validated(profile):
    with pytest.raises(InvalidProfileError):
        TeacherStrokeGenerator(None)
    profile.ink = (0, 256, 0)
    with pytest.raises(InvalidProfileError):
        TeacherStrokeGenerator(profile)


def test_all_strokes_and_single_point_dots_preserved(profile):
    result = render_teacher_strokes('iA.!', profile, options=opts())
    for placement in result.placements:
        original = profile.strokes[placement.character]
        assert [len(s) for s in placement.strokes] == [len(s) for s in original]
        # Each path is a uniform scale+translation: no reordering/dropped points.
        for src, out in zip(original, placement.strokes):
            for (sx, sy), (x, y) in zip(src, out):
                assert x - out[0][0] == pytest.approx((sx - src[0][0]) * 20)
                assert y - out[0][1] == pytest.approx((sy - src[0][1]) * 20)
    dot = result.placements[2].strokes[0][0]
    assert result.pages[0].getpixel((int(dot[0]), int(dot[1]))) == (0, 0, 0)


def test_default_never_joins_and_opt_in_uses_actual_endpoints():
    p = WriterProfile(ink=(0, 0, 0), strokes={
        'a': [[(0, 0), (0, 1)]], 'b': [[(0, 0), (0, 1)]],
    })
    o = opts(letter_spacing=20, join_max_distance=100)
    default = render_teacher_strokes('ab', p, options=o, seed=10)
    assert default.joins == ()
    assert default.warnings == ()
    # An empty gap proves no unreported bridge is drawn by default.
    left, right = default.placements
    y = int(left.strokes[0][-1][1])
    mid_x = int((left.strokes[0][-1][0] + right.strokes[0][0][0]) / 2)
    assert default.pages[0].getpixel((mid_x, y)) == (255, 255, 255)
    enabled = render_teacher_strokes('ab', p, options=replace(o, enable_heuristic_joins=True, join_probability=1), seed=10)
    assert len(enabled.joins) == 1
    join = enabled.joins[0]
    assert join.start == enabled.placements[0].strokes[-1][-1]
    assert join.end == enabled.placements[1].strokes[0][0]
    assert (join.from_offset, join.to_offset) == (0, 1)
    assert 'synthetic' in enabled.warnings[0].lower()
    midpoint = (int((join.start[0] + join.end[0]) / 2), int((join.start[1] + join.end[1]) / 2))
    assert enabled.pages[0].getpixel(midpoint) == (0, 0, 0)


def test_opt_in_never_connects_detached_dots_spaces_punctuation_or_wraps(profile):
    o = opts(enable_heuristic_joins=True, join_probability=1, join_max_distance=512)
    # i has a separate dot; j is only a dot. Neither is eligible.
    result = render_teacher_strokes('abiaja a.b\nab', profile, options=o)
    assert [(j.from_offset, j.to_offset) for j in result.joins] == [(0, 1), (11, 12)]
    assert all(j.start == next(p for p in result.placements if p.offset == j.from_offset).strokes[-1][-1]
               and j.end == next(p for p in result.placements if p.offset == j.to_offset).strokes[0][0]
               for j in result.joins)
    narrow = opts(page_width=44, page_height=200, enable_heuristic_joins=True,
                  join_probability=1, join_max_distance=512)
    wrapped = render_teacher_strokes('ababab', profile, options=narrow)
    for join in wrapped.joins:
        a = next(p for p in wrapped.placements if p.offset == join.from_offset)
        b = next(p for p in wrapped.placements if p.offset == join.to_offset)
        assert (a.page_index, a.line_index) == (b.page_index, b.line_index)
    assert any(a.line_index != b.line_index for a, b in zip(wrapped.placements, wrapped.placements[1:]))


def test_long_text_wraps_and_paginates_without_omission_and_with_ink_in_bounds(profile):
    o = opts(page_width=96, page_height=62, margin=4, line_height=26,
             em_size=14, letter_spacing=2, space_advance=8,
             size_jitter=0.1, baseline_jitter=1, max_pages=64)
    text = 'abA.i,! ' * 31 + '\n' + 'a' * 101 + '\t' + 'b' * 18
    result = render_teacher_strokes(text, profile, options=o, seed=87)
    assert len(result.pages) > 2
    expected = [(i, ch) for i, ch in enumerate(text) if ch not in ' \t\n']
    assert [(p.offset, p.character) for p in result.placements] == expected
    assert len({p.offset for p in result.placements}) == len(expected)
    assert any(a.line_index != b.line_index or a.page_index != b.page_index
               for a, b in zip(result.placements, result.placements[1:]))
    left, top, right, bottom = result.drawable_bounds
    for p in result.placements:
        assert 0 <= p.page_index < len(result.pages)
        l, t, r, b = p.bounds
        assert left <= l <= r <= right
        assert top <= t <= b <= bottom
        assert all(left <= x <= right and top <= y <= bottom for stroke in p.strokes for x, y in stroke)
    for page in result.pages:
        assert page.size == (o.page_width, o.page_height)
        non_background = Image.eval(page.convert('L'), lambda v: 255 if v != 255 else 0).getbbox()
        if non_background:
            x1, y1, x2, y2 = non_background
            assert x1 >= left and y1 >= top and x2 - 1 <= right and y2 - 1 <= bottom


@pytest.mark.parametrize('stroke_width', [1, 2, 3, 4, 9, 16, 31, 32])
def test_thick_extreme_source_paths_and_joins_remain_inside_pixels(stroke_width):
    profile = WriterProfile(ink=(0, 0, 0), strokes={
        'a': [[(-2, -2), (2, 2)]], 'b': [[(-2, 2), (2, -2)]],
    })
    o = opts(page_width=200, page_height=200, margin=8, line_height=110,
             em_size=9, stroke_width=stroke_width, enable_heuristic_joins=True,
             join_probability=1, join_max_distance=512)
    result = render_teacher_strokes('ababa\nabab', profile, options=o, seed=12)
    assert result.joins
    l, t, r, b = result.drawable_bounds
    for page in result.pages:
        for y in range(page.height):
            for x in range(page.width):
                if page.getpixel((x, y)) != (255, 255, 255):
                    assert l <= x <= r and t <= y <= b


def test_seed_repeatability_variation_and_profile_snapshot(profile):
    o = opts(size_jitter=0.15, baseline_jitter=2, line_height=40)
    gen = TeacherStrokeGenerator(profile, o)
    a = gen.render('abA.i! ab', seed=42)
    b = gen.render('abA.i! ab', seed=42)
    c = gen.render('abA.i! ab', seed=43)
    assert a.placements == b.placements and a.joins == b.joins
    assert [page.tobytes() for page in a.pages] == [page.tobytes() for page in b.pages]
    assert a.placements != c.placements
    profile.strokes['a'][0][0] = (1, 1)
    profile.strokes.clear()
    assert gen.render('abA.i! ab', seed=42).placements == a.placements


def test_blank_layout_and_unsupported_controls(profile):
    result = render_teacher_strokes('', profile, options=opts())
    assert len(result.pages) == 1 and result.placements == () and result.joins == ()
    whitespace = render_teacher_strokes(' \t\n  ', profile, options=opts())
    assert whitespace.placements == ()
    with pytest.raises(UnsupportedTextError) as caught:
        render_teacher_strokes('\r\v\f\x1b\u2028', profile, options=opts())
    assert all(x.reason == 'unsupported_whitespace_or_control' for x in caught.value.unsupported)


@pytest.mark.parametrize('changes', [
    {'page_width': 0}, {'page_height': 4097}, {'page_width': 3000, 'page_height': 3000},
    {'margin': 100}, {'line_height': 0}, {'stroke_width': 0}, {'stroke_width': True},
    {'em_size': float('nan')}, {'em_size': float('inf')}, {'em_size': -1},
    {'size_jitter': 0.3}, {'baseline_jitter': -1}, {'letter_spacing': -1},
    {'space_advance': 0}, {'join_probability': 1.1}, {'join_max_distance': -1},
    {'enable_heuristic_joins': 1}, {'max_pages': 65}, {'max_characters': 20001},
    {'background': (255, 255, 256)},
])
def test_invalid_options_rejected(profile, changes):
    with pytest.raises(ValueError):
        TeacherStrokeGenerator(profile, opts(**changes))


def test_layout_limits_and_failures_allocate_no_pages(profile, monkeypatch):
    monkeypatch.setattr(Image, 'new', lambda *a, **k: pytest.fail('allocated before layout failure'))
    with pytest.raises(LayoutError, match='max_characters'):
        render_teacher_strokes('aaa', profile, options=opts(max_characters=2))
    with pytest.raises(LayoutError, match='page count'):
        render_teacher_strokes('a\na\na', profile, options=opts(max_pages=1))
    with pytest.raises(LayoutError, match='line_height'):
        render_teacher_strokes('a', profile, options=opts(line_height=10))
    with pytest.raises(LayoutError, match='wider'):
        render_teacher_strokes('a', profile, options=opts(page_width=32, em_size=100, line_height=120, page_height=140))
    with pytest.raises(LayoutError, match='whitespace'):
        render_teacher_strokes('\t', profile, options=opts(page_width=40, space_advance=20))
    with pytest.raises(ValueError, match='seed'):
        render_teacher_strokes('a', profile, options=opts(), seed=True)
    with pytest.raises(ValueError, match='background'):
        render_teacher_strokes('a', profile, options=opts(background=(0, 0, 0)))


def test_total_page_pixel_and_transformed_point_budgets_fail_preallocation(profile, monkeypatch):
    monkeypatch.setattr(Image, 'new', lambda *a, **k: pytest.fail('allocated before resource failure'))
    huge = opts(page_width=2048, page_height=2048, margin=0, line_height=2048,
                max_pages=20)
    with pytest.raises(LayoutError, match='total pixel budget'):
        render_teacher_strokes('\n' * 8, profile, options=huge)
    many_points = WriterProfile(strokes={'a': [[(0, 0)] * 1000]})
    with pytest.raises(LayoutError, match='point budget'):
        render_teacher_strokes('a' * 501, many_points, options=opts())


def test_word_lookahead_moves_fitting_word_intact(profile):
    # 'a ' leaves enough room for the first glyph of 'ab', but not the word.
    # The complete word fits on a fresh line, so lookahead should keep it intact.
    o = opts(page_width=64, page_height=140, line_height=36, max_pages=4)
    text = 'a ab'
    result = render_teacher_strokes(text, profile, options=o)
    by_offset = {p.offset: p for p in result.placements}
    assert by_offset[0].line_index == 0
    assert by_offset[2].line_index == by_offset[3].line_index == 1
    assert [(p.offset, p.character) for p in result.placements] == [(0, 'a'), (2, 'a'), (3, 'b')]
    repeated = render_teacher_strokes(text, profile, options=o)
    assert result.placements == repeated.placements
    assert [page.tobytes() for page in result.pages] == [page.tobytes() for page in repeated.pages]
