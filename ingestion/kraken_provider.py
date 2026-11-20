"""Optional CPU-first Kraken HTR adapter.

The model weights are deliberately supplied by the deployment operator through
DL_KRAKEN_MODEL. No model is downloaded implicitly and no external paid API is
called. Kraken must return per-character cuts; line text without character
geometry is not sufficient evidence for personalized font compilation.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Sequence

import cv2
import numpy as np


class KrakenUnavailable(RuntimeError):
    """The optional Kraken runtime or its configured model is unavailable."""


class _HocrLineParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_line = False
        self.depth = 0
        self.text_parts: List[str] = []
        self.boxes: List[List[int]] = []
        self.confidences: List[float] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        values = dict(attrs)
        classes = values.get("class", "").split()
        if "ocr_line" in classes and not self.in_line:
            self.in_line = True
            self.depth = 1
            raw_boxes = values.get("x_bboxes", "")
            raw_conf = values.get("x_conf", "")
            self.boxes = _parse_boxes(raw_boxes)
            self.confidences = _parse_confidences(raw_conf)
        elif self.in_line:
            self.depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self.in_line:
            self.depth -= 1
            if self.depth <= 0:
                self.in_line = False

    def handle_data(self, data: str) -> None:
        if self.in_line:
            self.text_parts.append(data)

    @property
    def text(self) -> str:
        return re.sub(r"\s+", " ", "".join(self.text_parts)).strip()


def _parse_boxes(value: str) -> List[List[int]]:
    boxes: List[List[int]] = []
    # Kraken hOCR x_bboxes contains one x1,y1,x2,y2 tuple per character.
    for match in re.finditer(r"(-?\d+)\s*[, ]\s*(-?\d+)\s*[, ]\s*(-?\d+)\s*[, ]\s*(-?\d+)", value):
        x1, y1, x2, y2 = map(int, match.groups())
        if x2 > x1 and y2 > y1:
            boxes.append([x1, y1, x2 - x1, y2 - y1])
    return boxes


def _parse_confidences(value: str) -> List[float]:
    values = []
    for token in re.split(r"[,;\s]+", value.strip()):
        if not token:
            continue
        try:
            number = float(token)
        except ValueError:
            continue
        # Kraken confidence attributes may be percentages or probabilities.
        values.append(max(0.0, min(1.0, number / 100.0 if number > 1 else number)))
    return values


class KrakenCLIRecognizer:
    """Recognize already segmented line crops and require character-level cuts."""

    name = "kraken-htr"

    def __init__(self, model_path: str | Path | None = None,
                 executable: str = "kraken", timeout_seconds: int = 90):
        configured = model_path or os.getenv("DL_KRAKEN_MODEL")
        self.model_path = Path(configured).expanduser() if configured else None
        self.executable = executable
        self.timeout_seconds = timeout_seconds

    @property
    def available(self) -> bool:
        return bool(
            self.model_path and self.model_path.is_file()
            and (shutil.which(self.executable) or Path(self.executable).is_file())
        )

    def recognize_lines(self, lines: Sequence[np.ndarray]) -> List[Dict[str, Any]]:
        if not self.available:
            raise KrakenUnavailable(
                "Kraken HTR is not installed or DL_KRAKEN_MODEL does not point to a model file."
            )
        results: List[Dict[str, Any]] = []
        with tempfile.TemporaryDirectory(prefix="dl-kraken-") as temp:
            root = Path(temp)
            for index, line in enumerate(lines):
                if not isinstance(line, np.ndarray) or line.size == 0:
                    raise ValueError(f"Line crop {index + 1} is empty.")
                source = root / f"line-{index:03d}.png"
                target = root / f"line-{index:03d}.html"
                image = line
                if image.ndim == 3:
                    image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                ok, encoded = cv2.imencode(".png", image)
                if not ok:
                    raise ValueError(f"Line crop {index + 1} could not be encoded.")
                source.write_bytes(encoded.tobytes())
                command = [
                    self.executable, "-i", str(source), str(target), "-h",
                    "ocr", "--no-segmentation", "-m", str(self.model_path),
                ]
                try:
                    completed = subprocess.run(
                        command, check=True, capture_output=True, text=True,
                        timeout=self.timeout_seconds,
                    )
                except subprocess.TimeoutExpired as exc:
                    raise KrakenUnavailable("Handwriting recognition timed out; try a smaller page.") from exc
                except (subprocess.CalledProcessError, OSError) as exc:
                    detail = getattr(exc, "stderr", "") or str(exc)
                    raise KrakenUnavailable(f"Kraken could not recognize this line: {detail[:400]}") from exc
                if not target.is_file():
                    raise KrakenUnavailable("Kraken did not produce its expected hOCR output.")
                parser = _HocrLineParser()
                parser.feed(target.read_text(encoding="utf-8"))
                text = parser.text
                visible = [char for char in text if not char.isspace()]
                boxes = parser.boxes
                confidences = parser.confidences
                # Never fabricate character boxes when the model/output format
                # does not expose one box per visible character.
                if len(boxes) != len(visible):
                    boxes = []
                    confidences = []
                elif len(confidences) != len(visible):
                    confidences = [0.0] * len(visible)
                average = sum(confidences) / len(confidences) if confidences else 0.0
                results.append({
                    "text": text,
                    "confidence": average,
                    "char_boxes": boxes,
                    "char_confidences": confidences,
                    "needs_review": True,
                    "provider": self.name,
                    "stderr": completed.stderr[-400:] if completed.stderr else "",
                })
        return results
