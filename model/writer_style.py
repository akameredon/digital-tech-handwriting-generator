"""Learn a reusable handwriting identity from limited, verified samples.

The learner is deliberately conservative: it only consumes samples with trusted
labels, extracts normalized trajectories and style statistics, and reports coverage
instead of pretending an incomplete profile is complete. The resulting profile is
compatible with ``renderer.stroke_handwriting.HandwritingRenderer``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple
import math

import cv2
import numpy as np

from renderer.stroke_handwriting import Stroke, WriterProfile


@dataclass(frozen=True)
class VerifiedGlyphSample:
    """A labeled crop whose label has been verified by the teacher."""

    label: str
    image: np.ndarray
    confidence: float = 1.0
    source: str = "verified"

    def __post_init__(self) -> None:
        if len(self.label) != 1:
            raise ValueError("Each verified sample must contain exactly one character label.")
        if self.image is None or self.image.size == 0:
            raise ValueError("A verified sample must contain a non-empty image.")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Sample confidence must be between 0 and 1.")


@dataclass
class StyleLearningResult:
    profile: WriterProfile
    coverage: Dict[str, int]
    missing: List[str]
    variant_count: int
    warnings: List[str] = field(default_factory=list)

    @property
    def coverage_ratio(self) -> float:
        total = len(self.coverage) + len(self.missing)
        return len(self.coverage) / total if total else 0.0

    def public_dict(self) -> Dict[str, Any]:
        return {
            "writer": self.profile.name,
            "coverage": self.coverage,
            "missing": self.missing,
            "coverage_ratio": round(self.coverage_ratio, 3),
            "variant_count": self.variant_count,
            "warnings": self.warnings,
        }


class WriterStyleLearner:
    """Infer a trajectory-based writer profile from a small labeled sample set."""

    def __init__(self, required_characters: str | None = None, min_confidence: float = 0.70):
        self.required_characters = required_characters or (
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:!?"
        )
        self.min_confidence = min_confidence

    @staticmethod
    def _binary(image: np.ndarray) -> np.ndarray:
        array = np.asarray(image)
        if array.ndim == 3:
            array = cv2.cvtColor(array, cv2.COLOR_BGR2GRAY)
        if array.dtype != np.uint8:
            array = cv2.normalize(array, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        # Accept both white-ink-on-black and ordinary dark ink on light paper.
        if float(np.mean(array)) < 127:
            ink = (array > 100).astype(np.uint8)
        else:
            ink = (array < 160).astype(np.uint8)
        ink = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
        return ink

    @classmethod
    def _trajectory(cls, image: np.ndarray) -> Stroke:
        """Extract a stable, normalized center trajectory from a labeled crop.

        The column-median path is robust for thin handwritten strokes and avoids
        converting the sample into a conventional font outline. Disconnected marks
        such as an i-dot are appended as short trajectories.
        """
        ink = cls._binary(image)
        ys, xs = np.where(ink > 0)
        if len(xs) < 5:
            raise ValueError("The sample has too little visible ink.")
        x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
        crop = ink[y0:y1 + 1, x0:x1 + 1]
        points: Stroke = []
        for x in range(crop.shape[1]):
            column = np.where(crop[:, x] > 0)[0]
            if len(column):
                points.append((float(x), float(np.median(column))))
        if len(points) < 2:
            raise ValueError("The sample does not contain a recoverable trajectory.")
        w, h = max(1, x1 - x0), max(1, y1 - y0)
        normalized = [(round(x / w, 5), round(y / h, 5)) for x, y in points]
        # Preserve detached components as small marks at their normalized centroid.
        components, labels, stats, centroids = cv2.connectedComponentsWithStats(crop, 8)
        for component in range(1, components):
            area = stats[component, cv2.CC_STAT_AREA]
            if area >= 3 and stats[component, cv2.CC_STAT_WIDTH] < max(4, crop.shape[1] // 5):
                cx, cy = centroids[component]
                mark = (round(float(cx / w), 5), round(float(cy / h), 5))
                if all(math.dist(mark, p) > 0.035 for p in normalized):
                    normalized.extend([mark, (mark[0] + 0.008, mark[1] + 0.002)])
        return normalized

    @classmethod
    def _style_stats(cls, samples: Sequence[VerifiedGlyphSample]) -> Dict[str, float]:
        heights, widths, slants, densities = [], [], [], []
        for sample in samples:
            ink = cls._binary(sample.image)
            ys, xs = np.where(ink > 0)
            if len(xs) < 5:
                continue
            heights.append(float(ys.max() - ys.min() + 1))
            widths.append(float(xs.max() - xs.min() + 1))
            # Regression of x against y estimates the writer's habitual slant.
            slants.append(float(np.polyfit(ys.astype(float), xs.astype(float), 1)[0]))
            densities.append(float(np.count_nonzero(ink) / ink.size))
        if not heights:
            return {"scale": 1.0, "slant": 0.10, "stroke_width": 3.0, "pressure": 0.22}
        median_height = max(1.0, float(np.median(heights)))
        median_density = float(np.median(densities))
        return {
            "scale": max(0.65, min(1.45, median_height / 48.0)),
            "slant": max(-0.35, min(0.35, float(np.median(slants)) * 0.12)),
            "stroke_width": max(1.5, min(7.0, 1.4 + median_density * 38.0)),
            "pressure": max(0.08, min(0.45, float(np.std(densities)) * 7.0 + 0.12)),
        }

    def fit(
        self,
        samples: Iterable[VerifiedGlyphSample | Mapping[str, Any]],
        writer_name: str = "learned-writer",
    ) -> StyleLearningResult:
        normalized: List[VerifiedGlyphSample] = []
        warnings: List[str] = []
        for raw in samples:
            sample = raw if isinstance(raw, VerifiedGlyphSample) else VerifiedGlyphSample(
                label=str(raw.get("label", "")),
                image=np.asarray(raw.get("image")),
                confidence=float(raw.get("confidence", 1.0)),
                source=str(raw.get("source", raw.get("label_source", "verified"))),
            )
            if sample.confidence < self.min_confidence:
                warnings.append(f"Skipped low-confidence sample {sample.label!r}.")
                continue
            try:
                self._trajectory(sample.image)
            except ValueError as exc:
                warnings.append(f"Skipped {sample.label!r}: {exc}")
                continue
            normalized.append(sample)

        by_label: Dict[str, List[Stroke]] = {}
        accepted_samples: List[VerifiedGlyphSample] = []
        for sample in normalized:
            try:
                by_label.setdefault(sample.label, []).append(self._trajectory(sample.image))
                accepted_samples.append(sample)
            except ValueError:
                continue

        # Pick the highest-quality variant as the primary trajectory. Keep extra
        # variants available for a later stochastic variant selector.
        strokes = {label: [variants[0]] for label, variants in by_label.items() if variants}
        stats = self._style_stats(accepted_samples)
        profile = WriterProfile(name=writer_name, strokes=strokes, **stats)
        coverage = {label: len(variants) for label, variants in sorted(by_label.items())}
        missing = [char for char in self.required_characters if char not in coverage]
        if missing:
            warnings.append(
                f"Profile is incomplete: {len(missing)} required characters are missing; "
                "unseen text using them will use the renderer fallback trajectory."
            )
        if len(accepted_samples) < 12:
            warnings.append("Limited sample count; add repeated words and connected letter pairs for stronger identity.")
        return StyleLearningResult(profile, coverage, missing, len(accepted_samples), warnings)
