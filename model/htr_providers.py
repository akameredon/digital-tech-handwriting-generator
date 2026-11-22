"""Optional local HTR provider implementations.

The application core depends only on :class:`model.htr.HTRProvider`.  This
module contains integrations for heavyweight ML runtimes so importing the
application never downloads a model or requires PyTorch/Transformers.

The first supported provider is Microsoft's TrOCR through Hugging Face
Transformers.  It recognizes already-segmented line crops; page and character
segmentation remain separate responsibilities.  Model loading is explicit and
local-cache-only by default so production cannot unexpectedly fetch a large
artifact during a request.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import numpy as np
from PIL import Image


class HTRProviderConfigurationError(RuntimeError):
    """The optional provider cannot be used with the supplied configuration."""


@dataclass(frozen=True)
class TrOCRConfig:
    """Runtime settings for a local TrOCR line recognizer.

    ``local_files_only`` defaults to true deliberately.  Deployments must make
    model acquisition a visible build/deployment step, not a hidden request
    side effect.
    """

    model_id: str = "microsoft/trocr-small-handwritten"
    device: str = "cpu"
    local_files_only: bool = True
    num_threads: Optional[int] = None
    max_new_tokens: int = 128


class TrOCRProvider:
    """Recognize handwritten line crops with a locally available TrOCR model.

    The imports are lazy because the base application does not require the
    optional ``torch`` and ``transformers`` packages.  A clear configuration
    error is raised instead of silently falling back to another recognizer.
    """

    name = "trocr"

    def __init__(self, config: TrOCRConfig | None = None, *, model: Any = None, processor: Any = None):
        self.config = config or TrOCRConfig()
        self._model = model
        self._processor = processor
        self._torch = None

    @property
    def model_id(self) -> str:
        return self.config.model_id

    def _load(self) -> None:
        if self._model is not None and self._processor is not None:
            return
        try:
            import torch
            from transformers import TrOCRProcessor, VisionEncoderDecoderModel
        except ImportError as exc:  # pragma: no cover - exercised in deployment
            raise HTRProviderConfigurationError(
                "TrOCR requires optional packages 'torch' and 'transformers'. "
                "Install the HTR extra before enabling this provider."
            ) from exc

        if self.config.device != "cpu" and not torch.cuda.is_available():
            raise HTRProviderConfigurationError(
                f"Configured device {self.config.device!r} is unavailable on this host."
            )
        if self.config.num_threads is not None:
            if self.config.num_threads < 1:
                raise HTRProviderConfigurationError("num_threads must be at least 1.")
            torch.set_num_threads(self.config.num_threads)

        try:
            self._processor = TrOCRProcessor.from_pretrained(
                self.config.model_id, local_files_only=self.config.local_files_only
            )
            self._model = VisionEncoderDecoderModel.from_pretrained(
                self.config.model_id, local_files_only=self.config.local_files_only
            )
        except Exception as exc:  # pragma: no cover - depends on local model cache
            raise HTRProviderConfigurationError(
                f"Could not load local TrOCR model {self.config.model_id!r}. "
                "Preinstall the model or explicitly allow model download during provisioning."
            ) from exc

        self._torch = torch
        self._model.to(self.config.device)
        self._model.eval()

    @staticmethod
    def _to_pil(line: np.ndarray) -> Image.Image:
        if not isinstance(line, np.ndarray) or line.size == 0:
            raise ValueError("Each HTR line must be a non-empty numpy image array.")
        image = line
        if image.ndim == 2:
            image = np.repeat(image[:, :, None], 3, axis=2)
        elif image.ndim == 3 and image.shape[2] == 1:
            image = np.repeat(image, 3, axis=2)
        elif image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("Each HTR line must be grayscale or RGB image data.")
        if image.dtype != np.uint8:
            image = np.clip(image, 0, 255).astype(np.uint8)
        return Image.fromarray(image)

    def recognize_lines(self, lines: Sequence[np.ndarray]) -> Sequence[Dict[str, Any]]:
        """Return one transcription and confidence mapping per line crop.

        TrOCR exposes token scores rather than a calibrated document-level
        probability.  We therefore return a conservative mean token
        probability when available and let ``HTRPipeline`` decide whether the
        result requires teacher review.
        """
        self._load()
        assert self._processor is not None and self._model is not None and self._torch is not None
        images = [self._to_pil(line) for line in lines]
        if not images:
            return []
        inputs = self._processor(images=images, return_tensors="pt").pixel_values
        inputs = inputs.to(self.config.device)
        with self._torch.inference_mode():
            generated = self._model.generate(
                inputs,
                max_new_tokens=self.config.max_new_tokens,
                return_dict_in_generate=True,
                output_scores=True,
            )
        texts = self._processor.batch_decode(generated.sequences, skip_special_tokens=True)
        confidences = self._sequence_confidences(generated)
        return [
            {"text": text.strip(), "confidence": confidence, "provider": self.name}
            for text, confidence in zip(texts, confidences)
        ]

    @staticmethod
    def _sequence_confidences(generated: Any) -> list[float]:
        """Estimate a conservative sequence confidence from generation scores."""
        scores = getattr(generated, "scores", None)
        sequences = getattr(generated, "sequences", None)
        if not scores or sequences is None:
            return [0.0] * (len(sequences) if sequences is not None else 0)
        try:
            import torch
            token_count = min(len(scores), max(0, sequences.shape[1] - 1))
            if token_count == 0:
                return [0.0] * sequences.shape[0]
            values = []
            for row in range(sequences.shape[0]):
                token_probs = []
                for step in range(token_count):
                    distribution = torch.softmax(scores[step][row], dim=-1)
                    token_id = int(sequences[row, step + 1])
                    token_probs.append(float(distribution[token_id].item()))
                values.append(sum(token_probs) / len(token_probs))
            return values
        except Exception:
            # A confidence failure must cause review, never false certainty.
            return [0.0] * sequences.shape[0]


def trocr_from_environment() -> TrOCRProvider:
    """Build a provider from explicit environment configuration.

    This helper does not load the model.  It only parses configuration so the
    caller can decide when and where resource-heavy initialization occurs.
    """
    local_only = os.getenv("HTR_TROCR_LOCAL_FILES_ONLY", "1").lower() not in {"0", "false", "no"}
    threads = os.getenv("HTR_TROCR_THREADS")
    return TrOCRProvider(TrOCRConfig(
        model_id=os.getenv("HTR_TROCR_MODEL", TrOCRConfig.model_id),
        device=os.getenv("HTR_TROCR_DEVICE", "cpu"),
        local_files_only=local_only,
        num_threads=int(threads) if threads else None,
        max_new_tokens=int(os.getenv("HTR_TROCR_MAX_NEW_TOKENS", "128")),
    ))


@dataclass(frozen=True)
class KrakenConfig:
    """Explicit local Kraken model configuration."""

    model_path: str
    device: str = "cpu"


class KrakenProvider:
    """Recognize line crops with Kraken character cuts.

    Kraken's recognition records expose a prediction, per-character cuts, and
    confidences. Those cuts are converted to the provider-neutral
    ``character_boxes`` contract. A missing or malformed cut is preserved as
    invalid geometry so the alignment stage requests review instead of
    shifting later labels by position.
    """

    name = "kraken"

    def __init__(self, config: KrakenConfig, *, model: Any = None, recognizer: Any = None):
        self.config = config
        self._model = model
        self._recognizer = recognizer

    @property
    def model_id(self) -> str:
        return self.config.model_path

    @staticmethod
    def _to_pil(line: np.ndarray) -> Image.Image:
        return TrOCRProvider._to_pil(line)

    def _load(self) -> None:
        if self._model is not None and self._recognizer is not None:
            return
        try:
            from kraken import rpred
            from kraken.lib import models
        except ImportError as exc:  # pragma: no cover - depends on optional runtime
            raise HTRProviderConfigurationError(
                "Kraken requires the optional 'kraken' package before it can be enabled."
            ) from exc
        if not Path(self.config.model_path).is_file():
            raise HTRProviderConfigurationError(
                f"Kraken model file was not found: {self.config.model_path}"
            )
        try:
            self._model = models.load_any(self.config.model_path, device=self.config.device)
        except Exception as exc:  # pragma: no cover - depends on local model
            raise HTRProviderConfigurationError(
                f"Could not load the local Kraken model {self.config.model_path!r}."
            ) from exc
        self._recognizer = rpred.rpred

    @staticmethod
    def _bbox(cut: Any) -> Optional[list[int]]:
        if cut is None:
            return None
        points = cut
        if isinstance(cut, dict):
            points = cut.get("bbox", cut.get("polygon"))
        if not isinstance(points, (list, tuple)) or len(points) < 2:
            return None
        try:
            if len(points) == 4 and all(isinstance(value, (int, float)) for value in points):
                x, y, width, height = (int(value) for value in points)
                return [x, y, width, height]
            xs = [int(point[0]) for point in points]
            ys = [int(point[1]) for point in points]
            return [min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1]
        except (TypeError, ValueError, IndexError):
            return None

    def _recognize_one(self, line: np.ndarray) -> Dict[str, Any]:
        image = self._to_pil(line)
        width, height = image.size
        segmentation = {"type": "box", "boxes": [(0, 0, width, height)]}
        records = list(self._recognizer(self._model, image, segmentation))
        if len(records) != 1:
            raise RuntimeError("Kraken returned an unexpected number of line records.")
        record = records[0]
        text = str(getattr(record, "prediction", ""))
        cuts = list(getattr(record, "cuts", []) or [])
        confidences = list(getattr(record, "confidences", []) or [])
        boxes: list[Dict[str, Any]] = []
        visible_scores: list[float] = []
        for index, character in enumerate(text):
            if character.isspace():
                continue
            confidence = float(confidences[index]) if index < len(confidences) else 0.0
            bbox = self._bbox(cuts[index]) if index < len(cuts) else None
            boxes.append({"bbox": bbox, "confidence": confidence})
            visible_scores.append(confidence)
        return {
            "text": text,
            "confidence": sum(visible_scores) / len(visible_scores) if visible_scores else 0.0,
            "character_boxes": boxes,
            "character_geometry_mismatch": len(cuts) != len(text),
            "provider": self.name,
        }

    def recognize_lines(self, lines: Sequence[np.ndarray]) -> Sequence[Dict[str, Any]]:
        self._load()
        return [self._recognize_one(line) for line in lines]


def kraken_from_environment() -> KrakenProvider:
    """Create a lazy Kraken provider from an explicitly provisioned model path."""
    model_path = os.getenv("HTR_KRAKEN_MODEL", "")
    if not model_path:
        raise HTRProviderConfigurationError(
            "HTR_KRAKEN_MODEL must point to a provisioned local Kraken model file."
        )
    return KrakenProvider(KrakenConfig(
        model_path=model_path,
        device=os.getenv("HTR_KRAKEN_DEVICE", "cpu"),
    ))
