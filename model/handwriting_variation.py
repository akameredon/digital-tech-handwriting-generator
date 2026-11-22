"""Natural variation for handwriting trajectories and realization-level QA."""
from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Iterable, List, Sequence, Tuple

Point = Tuple[float, float]
Stroke = List[Point]


@dataclass(frozen=True)
class VariationConfig:
    size_jitter: float = 0.055
    slant_jitter: float = 0.035
    baseline_jitter: float = 0.04
    spacing_jitter: float = 0.035
    pressure_jitter: float = 0.22
    connection_jitter: float = 0.08


@dataclass(frozen=True)
class RealizedGlyph:
    strokes: Tuple[Tuple[Point, ...], ...]
    scale: float
    slant: float
    baseline: float
    pressure: float
    connection_offset: float


@dataclass(frozen=True)
class VariationMetrics:
    realizations: int
    mean_scale: float
    scale_std: float
    slant_std: float
    baseline_std: float
    pressure_std: float
    distinct_realizations: int

    @property
    def healthy(self) -> bool:
        return (
            self.realizations >= 2
            and self.distinct_realizations >= max(2, self.realizations // 2)
            and self.scale_std > 0.005
            and self.slant_std > 0.001
        )


class NaturalVariationController:
    """Create correlated, bounded variation without changing character identity."""

    def __init__(self, config: VariationConfig | None = None):
        self.config = config or VariationConfig()

    def realize(self, strokes: Sequence[Stroke], seed: int | None = None) -> RealizedGlyph:
        rng = random.Random(seed)
        scale = 1.0 + rng.uniform(-self.config.size_jitter, self.config.size_jitter)
        slant = rng.uniform(-self.config.slant_jitter, self.config.slant_jitter)
        baseline = rng.uniform(-self.config.baseline_jitter, self.config.baseline_jitter)
        pressure = 1.0 + rng.uniform(-self.config.pressure_jitter, self.config.pressure_jitter)
        connection = rng.uniform(-self.config.connection_jitter, self.config.connection_jitter)
        transformed: List[Tuple[Point, ...]] = []
        for stroke in strokes:
            transformed_stroke: List[Point] = []
            for x, y in stroke:
                # Slant about the x-height center. The same random field is used
                # for the whole glyph, creating natural writer-level coherence.
                transformed_stroke.append((
                    x * scale + (y - 0.55) * slant + connection,
                    y * scale + baseline,
                ))
            transformed.append(tuple(transformed_stroke))
        return RealizedGlyph(tuple(transformed), scale, slant, baseline, pressure, connection)

    def measure(self, strokes: Sequence[Stroke], seeds: Iterable[int]) -> VariationMetrics:
        realizations = [self.realize(strokes, seed) for seed in seeds]
        if not realizations:
            raise ValueError("At least one seed is required for variation measurement.")
        scales = [item.scale for item in realizations]
        slants = [item.slant for item in realizations]
        baselines = [item.baseline for item in realizations]
        pressures = [item.pressure for item in realizations]
        signatures = {tuple(round(value, 5) for stroke in item.strokes for point in stroke for value in point) for item in realizations}
        std = lambda values: math.sqrt(sum((value - sum(values) / len(values)) ** 2 for value in values) / len(values))
        return VariationMetrics(len(realizations), sum(scales) / len(scales), std(scales), std(slants), std(baselines), std(pressures), len(signatures))
