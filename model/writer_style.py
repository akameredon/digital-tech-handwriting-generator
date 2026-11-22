"""Learn experimental handwriting geometry from explicitly attested samples.

Static images cannot establish pen order, true pressure, or verified teacher likeness.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence
import json
import math
import cv2
import numpy as np
from renderer.stroke_handwriting import Stroke, WriterProfile

MAX_IMAGE_PIXELS = 16_000_000
MAX_INPUT_SAMPLES = 2048
MAX_TOTAL_SAMPLE_VALUES = 64_000_000
_VERIFIED_SOURCES = {
    "verified",
    "teacher",
    "trusted_worksheet",
    "worksheet_position",
    "human_verified",
}


def _trusted_source(source: Any) -> bool:
    return isinstance(source, str) and source.strip().lower() in _VERIFIED_SOURCES


def _validate_image(image: Any) -> np.ndarray:
    if image is None:
        raise ValueError("A sample must contain a non-empty image.")
    arr = np.asarray(image)
    if arr.ndim not in (2, 3) or (arr.ndim == 3 and arr.shape[2] not in (1, 3, 4)):
        raise ValueError("Image must be 2D grayscale or have 1, 3, or 4 channels.")
    if not arr.shape[0] or not arr.shape[1] or arr.shape[0] * arr.shape[1] > MAX_IMAGE_PIXELS:
        raise ValueError("Image dimensions are empty or exceed the supported pixel limit.")
    if arr.dtype.kind not in "uif" or not np.isfinite(arr).all():
        raise ValueError("Image pixels must be finite numeric values.")
    return arr


@dataclass(frozen=True)
class VerifiedGlyphSample:
    """Sample whose verified source is caller-attested, not cryptographically proven."""

    label: str
    image: np.ndarray
    confidence: float = 1.0
    source: str = "verified"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.label, str)
            or len(self.label) != 1
            or not self.label.isprintable()
            or self.label.isspace()
        ):
            raise ValueError("Each sample must have exactly one printable character label.")
        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not math.isfinite(self.confidence)
            or not 0 <= self.confidence <= 1
        ):
            raise ValueError("Sample confidence must be finite and between 0 and 1.")
        if not _trusted_source(self.source):
            raise ValueError("Sample source must be an explicitly trusted caller-attested source.")
        _validate_image(self.image)


@dataclass
class StyleLearningResult:
    profile: WriterProfile
    coverage: Dict[str, int]
    missing: List[str]
    variant_count: int
    warnings: List[str] = field(default_factory=list)
    variants: Dict[str, List[Stroke]] = field(default_factory=dict)

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

    def save_artifact(self, path: str | Path) -> None:
        p = {k: v for k, v in self.profile.__dict__.items() if k != "strokes"}
        p["ink"] = list(self.profile.ink)
        p["strokes"] = self.profile.strokes
        data = {
            "version": 1,
            "profile": p,
            "coverage": self.coverage,
            "missing": self.missing,
            "variant_count": self.variant_count,
            "warnings": self.warnings,
            "variants": self.variants,
        }
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load_artifact(cls, path: str | Path) -> "StyleLearningResult":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("version") != 1:
            raise ValueError("Unsupported style-learning artifact version.")
        p = data["profile"]
        p["ink"] = tuple(p.get("ink", (32, 45, 63)))
        p["strokes"] = {
            k: [[tuple(pt) for pt in stroke] for stroke in v] for k, v in p["strokes"].items()
        }
        profile = WriterProfile(**p)
        variants = {
            k: [[tuple(map(float, pt)) for pt in stroke] for stroke in v]
            for k, v in data["variants"].items()
        }
        return cls(
            profile,
            data["coverage"],
            data["missing"],
            int(data["variant_count"]),
            data.get("warnings", []),
            variants,
        )


class WriterStyleLearner:
    """Infer experimental static-image geometry from a small labeled sample set."""

    def __init__(self, required_characters: str | None = None, min_confidence: float = 0.70):
        if (
            isinstance(min_confidence, bool)
            or not isinstance(min_confidence, (int, float))
            or not math.isfinite(min_confidence)
            or not 0 <= min_confidence <= 1
        ):
            raise ValueError("min_confidence must be finite and between 0 and 1.")
        self.required_characters = (
            required_characters
            or "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:!?"
        )
        self.min_confidence = float(min_confidence)

    @staticmethod
    def _binary(image: np.ndarray) -> np.ndarray:
        array = _validate_image(image)
        if array.ndim == 3:
            if array.shape[2] == 1:
                array = array[:, :, 0]
            elif array.shape[2] == 4:
                array = cv2.cvtColor(array, cv2.COLOR_BGRA2GRAY)
            else:
                array = cv2.cvtColor(array, cv2.COLOR_BGR2GRAY)
        if array.dtype != np.uint8:
            array = cv2.normalize(array, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        ink = (
            (array > 100).astype(np.uint8)
            if float(np.mean(array)) < 127
            else (array < 160).astype(np.uint8)
        )
        return cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))

    @classmethod
    def _trajectory(cls, image: np.ndarray) -> Stroke:
        ink = cls._binary(image)
        ys, xs = np.where(ink > 0)
        if len(xs) < 5:
            raise ValueError("The sample has too little visible ink.")
        x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
        crop = ink[y0: y1 + 1, x0: x1 + 1]
        points = []
        for x in range(crop.shape[1]):
            col = np.where(crop[:, x] > 0)[0]
            if len(col):
                points.append((float(x), float(np.median(col))))
        if len(points) < 2:
            raise ValueError("The sample does not contain a recoverable trajectory.")
        w, h = max(1, x1 - x0), max(1, y1 - y0)
        normalized = [(round(x / w, 5), round(y / h, 5)) for x, y in points]
        n, _, stats, centers = cv2.connectedComponentsWithStats(crop, 8)
        for i in range(1, n):
            if stats[i, cv2.CC_STAT_AREA] >= 3 and stats[i, cv2.CC_STAT_WIDTH] < max(
                4, crop.shape[1] // 5
            ):
                cx, cy = centers[i]
                mark = (round(float(cx / w), 5), round(float(cy / h), 5))
                if all(math.dist(mark, p) > 0.035 for p in normalized):
                    normalized.extend([mark, (mark[0] + 0.008, mark[1] + 0.002)])
        return normalized

    @classmethod
    def _style_stats(cls, samples: Sequence[VerifiedGlyphSample]) -> Dict[str, float]:
        heights, slants, densities = [], [], []
        for sample in samples:
            ink = cls._binary(sample.image)
            ys, xs = np.where(ink > 0)
            if len(xs) < 5:
                continue
            crop = ink[ys.min(): ys.max() + 1, xs.min(): xs.max() + 1]
            heights.append(float(crop.shape[0]))
            slants.append(float(np.polyfit(ys.astype(float), xs.astype(float), 1)[0]))
            densities.append(float(np.count_nonzero(crop) / crop.size))
        if not heights:
            return {"scale": 1.0, "slant": 0.10, "stroke_width": 3.0, "pressure": 0.22}
        medh = max(1.0, float(np.median(heights)))
        density = float(np.median(densities))
        return {
            "scale": max(0.65, min(1.45, medh / 48)),
            "slant": round(max(-0.35, min(0.35, float(np.median(slants)) * 0.12)), 8),
            "stroke_width": max(1.5, min(7.0, 1.4 + density * 38)),
            "pressure": max(0.08, min(0.45, float(np.std(densities)) * 7 + 0.12)),
        }

    def fit(
        self,
        samples: Iterable[VerifiedGlyphSample | Mapping[str, Any]],
        writer_name: str = "learned-writer",
    ) -> StyleLearningResult:
        if (
            not isinstance(writer_name, str)
            or not writer_name.strip()
            or not writer_name.isprintable()
        ):
            raise ValueError("writer_name must be a non-empty printable string.")
        accepted = []
        warnings = []
        total_values = 0
        for index, raw in enumerate(samples):
            if index >= MAX_INPUT_SAMPLES:
                warnings.append(f"Stopped after the input sample limit of {MAX_INPUT_SAMPLES}.")
                break
            if isinstance(raw, VerifiedGlyphSample):
                sample = raw
            elif isinstance(raw, Mapping):
                try:
                    source = raw.get("source", raw.get("label_source", ""))
                    attested = raw.get("verified", raw.get("attested", False))
                    if (
                        not isinstance(attested, bool)
                        or not attested
                        or not _trusted_source(source)
                    ):
                        warnings.append(
                            "Skipped mapping sample without explicit verified caller attestation and trusted source."
                        )
                        continue
                    sample = VerifiedGlyphSample(
                        raw.get("label", ""), raw.get("image"), raw.get("confidence", 1.0), source
                    )
                except (ValueError, TypeError, AttributeError) as exc:
                    warnings.append(f"Skipped malformed mapping sample: {exc}")
                    continue
            else:
                warnings.append("Skipped unsupported sample type.")
                continue
            if sample.confidence < self.min_confidence:
                warnings.append(f"Skipped low-confidence sample {sample.label!r}.")
                continue
            sample_values = np.asarray(sample.image).size
            if total_values + sample_values > MAX_TOTAL_SAMPLE_VALUES:
                warnings.append(
                    f"Stopped at the total sample pixel-value limit of {MAX_TOTAL_SAMPLE_VALUES}."
                )
                break
            try:
                self._trajectory(sample.image)
            except (ValueError, TypeError, cv2.error) as exc:
                warnings.append(f"Skipped {sample.label!r}: {exc}")
                continue
            accepted.append(sample)
            total_values += sample_values
        variants: Dict[str, List[Stroke]] = {}
        for sample in accepted:
            variants.setdefault(sample.label, []).append(self._trajectory(sample.image))
        profile = WriterProfile(
            name=writer_name,
            strokes={k: [v[0]] for k, v in variants.items()},
            **self._style_stats(accepted),
        )
        coverage = {k: len(v) for k, v in sorted(variants.items())}
        missing = [c for c in self.required_characters if c not in coverage]
        if missing:
            warnings.append(
                "Profile is incomplete: {} required characters are missing; unseen text using them "
                "will use the renderer fallback trajectory.".format(len(missing))
            )
        if len(accepted) < 12:
            warnings.append(
                "Limited sample count; add repeated words and connected letter pairs for stronger identity."
            )
        return StyleLearningResult(profile, coverage, missing, len(accepted), warnings, variants)
