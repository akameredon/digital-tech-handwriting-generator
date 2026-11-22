from model.handwriting_variation import NaturalVariationController, VariationConfig


STROKES = [[(0.0, 0.8), (0.25, 0.1), (0.6, 0.8)], [(0.15, 0.55), (0.45, 0.55)]]


def test_variation_is_reproducible_but_not_stamped():
    controller = NaturalVariationController()
    first = controller.realize(STROKES, seed=12)
    repeat = controller.realize(STROKES, seed=12)
    other = controller.realize(STROKES, seed=13)
    assert first == repeat
    assert first != other
    assert abs(first.scale - 1.0) <= 0.055
    assert abs(first.slant) <= 0.035


def test_variation_metrics_detect_healthy_realizations():
    metrics = NaturalVariationController().measure(STROKES, range(20))
    assert metrics.realizations == 20
    assert metrics.distinct_realizations == 20
    assert metrics.healthy
    assert metrics.scale_std > 0
    assert metrics.slant_std > 0


def test_zero_jitter_is_identical_and_fails_natural_variation_gate():
    controller = NaturalVariationController(VariationConfig(
        size_jitter=0, slant_jitter=0, baseline_jitter=0,
        pressure_jitter=0, connection_jitter=0,
    ))
    metrics = controller.measure(STROKES, range(5))
    assert metrics.distinct_realizations == 1
    assert not metrics.healthy
