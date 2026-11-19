"""Index prepared lesson notes by the metadata inside each Markdown file."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Optional, Tuple

from curriculum.nerdc_schemes import get_lesson

LessonKey = Tuple[str, str, int]
_FIELD_PATTERN = re.compile(
    r"^\s*\*\*(Class|Term|Week|Topic):\*\*\s*(.*?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def _sample_root(samples_dir: Optional[Path] = None) -> Path:
    return Path(samples_dir) if samples_dir is not None else Path(__file__).resolve().parents[1] / "samples"


def _read_metadata(path: Path) -> Optional[Tuple[LessonKey, str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    fields = {name.casefold(): value.strip() for name, value in _FIELD_PATTERN.findall(text)}
    if not {"class", "term", "week", "topic"}.issubset(fields):
        return None
    try:
        week = int(fields["week"])
    except ValueError:
        return None
    return (fields["class"].upper(), fields["term"], week), fields["topic"]


def _topic_matches(sample_topic: str, official_topic: str) -> bool:
    """Accept a prepared note whose title is the curriculum topic or a clear extension."""
    sample = " ".join(sample_topic.casefold().split())
    official = " ".join(official_topic.casefold().split())
    if sample == official:
        return True
    if not sample.startswith(official):
        return False
    return sample[len(official):len(official) + 1] in {" ", "–", "—", "-", ":", "("}


def prepared_lesson_index(samples_dir: Optional[Path] = None) -> Dict[LessonKey, Path]:
    """Return only uniquely indexed notes that agree with the curriculum topic."""
    root = _sample_root(samples_dir)
    index: Dict[LessonKey, Path] = {}
    if not root.is_dir():
        return index

    for path in sorted(root.rglob("*.md")):
        metadata = _read_metadata(path)
        if metadata is None:
            continue
        key, sample_topic = metadata
        official = get_lesson(*key)
        if official is None or not _topic_matches(sample_topic, official["topic"]):
            continue
        if key in index:
            raise ValueError(
                f"More than one prepared lesson note claims {key}: {index[key]} and {path}"
            )
        index[key] = path
    return index


def get_prepared_lesson(
    class_level: str,
    term: str,
    week: int,
    samples_dir: Optional[Path] = None,
) -> Optional[str]:
    """Read a curriculum-matched prepared note, if one is available."""
    key = (class_level.upper(), term, week)
    path = prepared_lesson_index(samples_dir).get(key)
    return path.read_text(encoding="utf-8") if path else None
