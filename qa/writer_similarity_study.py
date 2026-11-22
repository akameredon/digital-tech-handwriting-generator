"""Build and analyze a *future* independent, blinded handwriting study.

No data or authenticity claim is supplied by this module. A source is a human-
verified, held-out phrase image; each candidate is an independently supplied
image for exactly that source text. Both attestations are supplied by the caller:
this code cannot establish data provenance, holdout separation, or transcription
correctness by inspecting pixels. Each source must have the same methods,
including the explicitly named generic baseline and at least one other method.
Identical images, including metadata-only variants, are rejected.

Example (paths below are illustrative, not bundled data)::

    import secrets

    sources = [SourcePhrase('s1', 'teacher-1', 'Hello!', 'heldout.png',
                            verified=True, held_out=True)]
    candidates = [Candidate('s1', 'generic', 'Hello!', 'generic.png',
                            text_verified=True),
                  Candidate('s1', 'proposed', 'Hello!', 'proposed.png',
                            text_verified=True)]
    paths = build_manifest(sources, candidates, baseline_method='generic',
                           seed=secrets.randbits(256), public_dir='reviewer-package',
                           private_key_path='secure/study-key.json')
    report = aggregate_ratings(paths.private_key_path, ['reviewer-1'], [
        Rating(candidate_id='<ID from reviewer manifest>',
               reviewer_id='reviewer-1', label='same_writer',
               legibility=4, similarity=3)])

Share only the reviewer-package directory. Keep the private key AND the seed
confidential until ratings are collected, and retain the key separately. Never
publish the unblinded report to reviewers before collection is complete. The
reviewer sees a reference image and candidate image, not the expected text;
labels express the reviewer's judgment, not a verified ground-truth identity.
Scores are ordinal integers 1 (low) through 5 (high), or None if unrated.

Images are composited onto white, re-encoded without file metadata or alpha
channels, and receive opaque filenames. The code cannot remove identifying information visible in the image
or rule out identifying visible text, distinctive strokes, or recognition by
the reviewer. The operator must inspect/redact these and obtain necessary consent;
reject images that cannot be safely shared. Small seeds are guessable; seeded
randomization is reproducibility, not cryptographic anonymization. Use a high-
entropy private seed. Select independent reviewers and a preregistered protocol outside
this module. Descriptive statistics are not acceptance gates or evidence of
real-world performance without real, representative data and appropriate study
analysis.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
import hmac
from io import BytesIO
from itertools import combinations
import json
import os
from pathlib import Path
import shutil
from statistics import mean, median
from typing import Iterable, Optional, Sequence

from PIL import Image, ImageOps, UnidentifiedImageError


LABELS = ("same_writer", "different_writer", "unsure")
SCORE_MIN, SCORE_MAX = 1, 5


@dataclass(frozen=True)
class SourcePhrase:
    source_id: str
    teacher_id: str
    text: str
    image_path: str | Path
    verified: bool
    held_out: bool


@dataclass(frozen=True)
class Candidate:
    source_id: str
    method: str
    text: str
    image_path: str | Path
    text_verified: bool


@dataclass(frozen=True)
class Rating:
    candidate_id: str
    reviewer_id: str
    label: Optional[str] = None
    legibility: Optional[int] = None
    similarity: Optional[int] = None


@dataclass(frozen=True)
class Assignment:
    candidate_id: str
    reviewer_id: str


@dataclass(frozen=True)
class StudyPaths:
    public_dir: Path
    manifest_path: Path
    private_key_path: Path


def _nonblank(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError(f"{name} must be a non-empty string without NUL")
    return value


def _image_snapshot(path: str | Path) -> tuple[bytes, str, str]:
    """Decode once, normalize orientation, strip metadata and fingerprint pixels."""
    if not isinstance(path, (str, Path)) or not str(path).strip():
        raise ValueError("image path must be a non-empty path")
    try:
        resolved = Path(path).resolve(strict=True)
        if not resolved.is_file():
            raise ValueError(f"image is not a regular file: {path}")
        with Image.open(resolved) as image:
            if getattr(image, "n_frames", 1) != 1:
                raise ValueError(f"animated or multi-frame image is not supported: {path}")
            image.load()
            oriented = ImageOps.exif_transpose(image)
            pixels = oriented.convert("RGBA")
            # Reject an image that is visually constant on a white page. This is
            # not a handwriting, transcription, or perceptual-quality check.
            on_white = Image.new("RGBA", pixels.size, "white")
            on_white.alpha_composite(pixels)
            visible = on_white.convert("RGB")
            if all(low == high for low, high in visible.getextrema()):
                raise ValueError(f"visibly blank or uniform image: {path}")
            # Hash and save what the reviewer will actually see on white, with no
            # alpha channel that could conceal data in fully transparent pixels.
            # A fresh image also drops EXIF, textual chunks and ICC profiles.
            clean = Image.new("RGB", visible.size)
            clean.paste(visible)
            digest = sha256((f"RGB:{clean.width}:{clean.height}:").encode() + clean.tobytes()).hexdigest()
            buffer = BytesIO()
            clean.save(buffer, format="PNG")
            return buffer.getvalue(), digest, str(resolved)
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ValueError(f"image cannot be read or decoded: {path}") from exc


class _BlindRandom:
    """Keyed deterministic stream; the secret seed must have high entropy."""

    def __init__(self, seed: int) -> None:
        self._key = sha256(f"writer-study-v1:{seed}".encode('ascii')).digest()
        self._counter = 0

    def _draw(self) -> bytes:
        block = hmac.digest(self._key, self._counter.to_bytes(16, 'big'), 'sha256')
        self._counter += 1
        return block

    def shuffle(self, items: list) -> None:
        for index in range(len(items) - 1, 0, -1):
            modulus = index + 1
            limit = (1 << 256) - ((1 << 256) % modulus)
            while True:
                number = int.from_bytes(self._draw(), 'big')
                if number < limit:
                    break
            chosen = number % modulus
            items[index], items[chosen] = items[chosen], items[index]

    def token(self) -> str:
        return self._draw()[:16].hex()


def _opaque_id(rng: _BlindRandom, prefix: str, seen: set[str]) -> str:
    while True:
        result = f"{prefix}-{rng.token()}"
        if result not in seen:
            seen.add(result)
            return result


def build_manifest(
    sources: Iterable[SourcePhrase],
    candidates: Iterable[Candidate],
    *,
    baseline_method: str,
    seed: int,
    public_dir: str | Path,
    private_key_path: str | Path,
) -> StudyPaths:
    """Write a blinded reviewer package and a separate 0600 private JSON key.

    The output directory and private key must not exist; their parents must
    already exist. All inputs are validated before outputs are created. Files
    are snapshotted once, and a failed write removes this call's partial output.
    Source text and teacher IDs are retained exactly in the private key and are
    not included in the public manifest. A candidate's declared text must be
    codepoint-for-codepoint equal to its source text (no normalization).
    The output is deterministic for identical input, file bytes and seed.
    """
    _nonblank(baseline_method, "baseline_method")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("seed must be an integer")
    try:
        source_list, candidate_list = list(sources), list(candidates)
    except TypeError as exc:
        raise ValueError("sources and candidates must be iterable") from exc
    if not source_list or not candidate_list:
        raise ValueError("at least one source and its candidates are required")
    if not all(isinstance(s, SourcePhrase) for s in source_list):
        raise ValueError("sources must contain only SourcePhrase instances")
    if not all(isinstance(c, Candidate) for c in candidate_list):
        raise ValueError("candidates must contain only Candidate instances")

    source_by_id: dict[str, SourcePhrase] = {}
    phrase_keys: set[tuple[str, str]] = set()
    for source in source_list:
        _nonblank(source.source_id, "source_id")
        _nonblank(source.teacher_id, "teacher_id")
        _nonblank(source.text, "source text")
        if source.verified is not True or source.held_out is not True:
            raise ValueError("every source must be verified and held out")
        if source.source_id in source_by_id:
            raise ValueError("duplicate source_id")
        if (source.teacher_id, source.text) in phrase_keys:
            raise ValueError("duplicate teacher and source text")
        source_by_id[source.source_id] = source
        phrase_keys.add((source.teacher_id, source.text))

    by_pair: dict[tuple[str, str], Candidate] = {}
    methods_by_source: dict[str, set[str]] = defaultdict(set)
    for candidate in candidate_list:
        _nonblank(candidate.source_id, "candidate source_id")
        _nonblank(candidate.method, "candidate method")
        _nonblank(candidate.text, "candidate text")
        if candidate.source_id not in source_by_id:
            raise ValueError("candidate references an unknown source")
        if candidate.text != source_by_id[candidate.source_id].text:
            raise ValueError("candidate text must exactly match the source text")
        if candidate.text_verified is not True:
            raise ValueError("candidate text must be independently verified")
        pair = (candidate.source_id, candidate.method)
        if pair in by_pair:
            raise ValueError("duplicate candidate for source and method")
        by_pair[pair] = candidate
        methods_by_source[candidate.source_id].add(candidate.method)
    method_sets = [methods_by_source[s.source_id] for s in source_list]
    if any(baseline_method not in methods or len(methods) < 2 for methods in method_sets):
        raise ValueError("each source needs the specified baseline and at least one comparator")
    if any(methods != method_sets[0] for methods in method_sets[1:]):
        raise ValueError("all sources must have the same methods")

    public_path = Path(public_dir).resolve()
    key_path = Path(private_key_path).resolve()
    if key_path == public_path or public_path in key_path.parents:
        raise ValueError("private key must be outside the public reviewer directory")
    if not public_path.parent.is_dir() or not key_path.parent.is_dir():
        raise ValueError("public and private output parents must already exist")
    if public_path.exists() or key_path.exists():
        raise ValueError("output directory and private key must not already exist")

    # Sorting makes input collection order irrelevant to the seeded result.
    source_list.sort(key=lambda s: s.source_id)
    candidate_list.sort(key=lambda c: (c.source_id, c.method))
    snapshots: dict[tuple[str, ...], tuple[bytes, str, str]] = {}
    seen_paths: set[str] = set()
    seen_pixels: set[str] = set()
    for key, image_path in (
        [(('source', s.source_id), s.image_path) for s in source_list]
        + [(('candidate', c.source_id, c.method), c.image_path) for c in candidate_list]
    ):
        snapshot = _image_snapshot(image_path)
        if snapshot[2] in seen_paths or snapshot[1] in seen_pixels:
            raise ValueError("duplicate image path or pixel content")
        snapshots[key] = snapshot
        seen_paths.add(snapshot[2])
        seen_pixels.add(snapshot[1])

    rng = _BlindRandom(seed)
    seen_ids: set[str] = set()
    shuffled_sources, shuffled_candidates = source_list[:], candidate_list[:]
    rng.shuffle(shuffled_sources)
    rng.shuffle(shuffled_candidates)
    ref_ids = {s.source_id: _opaque_id(rng, 'r', seen_ids) for s in shuffled_sources}
    candidate_ids = {(c.source_id, c.method): _opaque_id(rng, 'c', seen_ids)
                     for c in shuffled_candidates}
    references, public_candidates, private_sources, private_candidates = [], [], [], []
    files: dict[str, bytes] = {}
    for s in shuffled_sources:
        ref = ref_ids[s.source_id]
        data, fingerprint, path = snapshots[('source', s.source_id)]
        asset = f"assets/{ref}.png"
        files[asset] = data
        references.append({"reference_id": ref, "image": asset})
        private_sources.append({"reference_id": ref, "source_id": s.source_id,
                                "teacher_id": s.teacher_id, "text": s.text,
                                "input_image": path, "pixel_sha256": fingerprint})
    for c in shuffled_candidates:
        cid = candidate_ids[(c.source_id, c.method)]
        data, fingerprint, path = snapshots[('candidate', c.source_id, c.method)]
        asset = f"assets/{cid}.png"
        files[asset] = data
        public_candidates.append({"candidate_id": cid, "reference_id": ref_ids[c.source_id],
                                  "image": asset})
        private_candidates.append({"candidate_id": cid, "source_id": c.source_id,
                                   "method": c.method, "text": c.text,
                                   "input_image": path, "pixel_sha256": fingerprint})
    public_manifest = {
        "schema_version": 1,
        "references": references,
        "candidates": public_candidates,
        "label_options": list(LABELS),
        "protocol": [
            "First score candidate legibility from the candidate image alone, before consulting the reference image.",
            "Then compare the candidate with its linked reference; score similarity and judge whether they look like the same writer.",
            "Use unsure when you cannot decide. The labels are judgments, not claims of source or authenticity.",
            "Record null for any judgment not made; do not infer method or teacher identity from presentation order.",
        ],
        "score_scale": {"minimum": SCORE_MIN, "maximum": SCORE_MAX,
                        "meaning": "Integer scores; 1=low, 5=high; null=unrated",
                        "legibility": "1=very hard to read; 5=very easy to read",
                        "similarity": "1=very dissimilar to reference; 5=very similar to reference"},
    }
    key = {"schema_version": 1, "seed": seed, "baseline_method": baseline_method,
           "sources": private_sources, "candidates": private_candidates}

    created_dir = created_key = False
    try:
        # Handwriting may identify a teacher.  Even the blinded review package
        # stays private on disk until an operator deliberately shares it.
        public_path.mkdir(mode=0o700)
        created_dir = True
        (public_path / 'assets').mkdir(mode=0o700)
        for name, data in files.items():
            (public_path / name).write_bytes(data)
        (public_path / 'manifest.json').write_text(
            json.dumps(public_manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        # Atomic exclusive creation prevents overwriting existing keys or symlinks.
        fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created_key = True
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(key, out, ensure_ascii=False, indent=2)
            out.write('\n')
    except Exception:
        if created_key:
            key_path.unlink(missing_ok=True)
        if created_dir:
            shutil.rmtree(public_path)
        raise
    return StudyPaths(public_path, public_path / 'manifest.json', key_path)


def _load_key(path: str | Path) -> dict:
    try:
        with Path(path).open(encoding='utf-8') as f:
            key = json.load(f)
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError("private key cannot be read as JSON") from exc
    if not isinstance(key, dict) or key.get('schema_version') != 1:
        raise ValueError("invalid private key schema")
    try:
        baseline = _nonblank(key['baseline_method'], 'baseline method')
        source_records, candidate_records = key['sources'], key['candidates']
        if not isinstance(source_records, list) or not isinstance(candidate_records, list):
            raise ValueError("invalid key records")
        if not source_records or not candidate_records:
            raise ValueError("empty key")
        sources: dict[str, dict] = {}
        references: set[str] = set()
        for s in source_records:
            sid = _nonblank(s['source_id'], 'source ID')
            ref = _nonblank(s['reference_id'], 'reference ID')
            _nonblank(s['teacher_id'], 'teacher ID')
            _nonblank(s['text'], 'source text')
            if sid in sources or ref in references:
                raise ValueError("duplicate source or reference in key")
            sources[sid] = s
            references.add(ref)
        candidates: dict[str, dict] = {}
        pairs: set[tuple[str, str]] = set()
        by_source: dict[str, set[str]] = defaultdict(set)
        for c in candidate_records:
            cid = _nonblank(c['candidate_id'], 'candidate ID')
            sid = _nonblank(c['source_id'], 'source ID')
            method = _nonblank(c['method'], 'method')
            if cid in candidates or cid in references or (sid, method) in pairs:
                raise ValueError("duplicate candidate in key")
            if sid not in sources or c['text'] != sources[sid]['text']:
                raise ValueError("invalid candidate source or text in key")
            candidates[cid] = {**c, 'teacher_id': sources[sid]['teacher_id']}
            pairs.add((sid, method))
            by_source[sid].add(method)
        method_sets = [by_source[sid] for sid in sources]
        if any(baseline not in methods or len(methods) < 2 for methods in method_sets):
            raise ValueError("missing baseline or comparator in key")
        if any(methods != method_sets[0] for methods in method_sets[1:]):
            raise ValueError("unbalanced methods in key")
        return {'baseline': baseline, 'sources': sources, 'candidates': candidates}
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("invalid private key records") from exc


def _rating_value(value: object, field: str) -> None:
    if value is not None and (not isinstance(value, int) or isinstance(value, bool)
                              or not SCORE_MIN <= value <= SCORE_MAX):
        raise ValueError(f"{field} must be an integer from 1 to 5 or None")


def _score_summary(values: list[int]) -> dict:
    counts = Counter(values)
    return {'n': len(values), 'mean': mean(values) if values else None,
            'median': median(values) if values else None,
            'distribution': {str(i): counts[i] for i in range(SCORE_MIN, SCORE_MAX + 1)}}


def _inter_rater(candidate_ids: Sequence[str], observations: dict[tuple[str, str], Rating]) -> dict:
    by_candidate: dict[str, list[Rating]] = defaultdict(list)
    selected = set(candidate_ids)
    for (cid, _), rating in observations.items():
        if cid in selected:
            by_candidate[cid].append(rating)
    result = {}
    for field in ('label', 'legibility', 'similarity'):
        pairs, item_count, equal, absolute_differences = 0, 0, 0, []
        for rows in by_candidate.values():
            values = [getattr(r, field) for r in rows if getattr(r, field) is not None]
            if len(values) >= 2:
                item_count += 1
            for left, right in combinations(values, 2):
                pairs += 1
                equal += left == right
                if field != 'label':
                    absolute_differences.append(abs(left - right))
        data = {'items_with_2_plus_ratings': item_count, 'rater_pairs': pairs,
                'exact_agreements': equal,
                'exact_agreement_rate': equal / pairs if pairs else None}
        if field != 'label':
            data['mean_absolute_difference'] = mean(absolute_differences) if pairs else None
        result[field] = data
    return result


def _summarize(candidate_ids: Sequence[str], candidates: dict[str, dict],
               assignments: set[tuple[str, str]], observations: dict[tuple[str, str], Rating]) -> dict:
    ids = set(candidate_ids)
    expected = {pair for pair in assignments if pair[0] in ids}
    present = {pair: rating for pair, rating in observations.items() if pair in expected}
    labels = Counter(r.label for r in present.values() if r.label is not None)
    n_labels = sum(labels.values())
    missing_fields = {field: sum(pair not in present or getattr(present[pair], field) is None
                                 for pair in expected)
                      for field in ('label', 'legibility', 'similarity')}
    assigned_ids = {cid for cid, _ in expected}
    return {
        'candidate_count': len(ids),
        'source_count': len({candidates[cid]['source_id'] for cid in ids}),
        'teacher_count': len({candidates[cid]['teacher_id'] for cid in ids}),
        'assigned_reviewers': len({reviewer for _, reviewer in expected}),
        'expected_rating_rows': len(expected), 'submitted_rating_rows': len(present),
        'missing_rating_rows': len(expected) - len(present),
        'unassigned_candidates': len(ids - assigned_ids),
        'missing_by_field': missing_fields,
        'labels': {'n': n_labels, 'counts': {label: labels[label] for label in LABELS},
                   'proportions': {label: labels[label] / n_labels if n_labels else None
                                   for label in LABELS}},
        'legibility': _score_summary([r.legibility for r in present.values() if r.legibility is not None]),
        'similarity': _score_summary([r.similarity for r in present.values() if r.similarity is not None]),
        'inter_rater': _inter_rater(candidate_ids, present),
    }


def _paired_summary(pairs: list[tuple[Rating, Rating]], expected: int) -> dict:
    result: dict = {'expected_source_reviewer_pairs': expected,
                    'matched_source_reviewer_pairs': len(pairs),
                    'missing_paired_submissions': expected - len(pairs)}
    for field in ('legibility', 'similarity'):
        diffs = [getattr(proposed, field) - getattr(base, field)
                 for proposed, base in pairs
                 if getattr(proposed, field) is not None and getattr(base, field) is not None]
        result[field] = {'n': len(diffs), 'mean_method_minus_baseline': mean(diffs) if diffs else None,
                         'median_method_minus_baseline': median(diffs) if diffs else None}
    label_pairs = [(p.label, b.label) for p, b in pairs if p.label is not None and b.label is not None]
    counts = Counter(label_pairs)
    result['labels'] = {
        'n': len(label_pairs),
        'method_by_baseline': {method: {base: counts[(method, base)] for base in LABELS}
                               for method in LABELS},
        'same_writer_rate_difference': (
            sum(p == 'same_writer' for p, _ in label_pairs) / len(label_pairs)
            - sum(b == 'same_writer' for _, b in label_pairs) / len(label_pairs)
            if label_pairs else None),
    }
    return result


def aggregate_ratings(
    private_key_path: str | Path,
    reviewers: Iterable[str],
    ratings: Iterable[Rating],
    *,
    assignments: Optional[Iterable[Assignment]] = None,
) -> dict:
    """Unblind and summarize ratings; the resulting report is NOT reviewer-safe.

    Each reviewer may submit at most one row per assigned candidate. Missing
    rows and individual null fields are both counted. By default every listed
    reviewer is assigned every candidate; provide explicit assignments for an
    incomplete design. Pairwise inter-rater agreement is descriptive, not
    chance-corrected, and uses all available reviewer pairs on the same image.
    Baseline contrasts match the same reviewer and held-out source only.
    """
    key = _load_key(private_key_path)
    candidates = key['candidates']
    try:
        reviewer_list = list(reviewers)
        rating_list = list(ratings)
        assignment_list = list(assignments) if assignments is not None else None
    except TypeError as exc:
        raise ValueError("reviewers, ratings, and assignments must be iterable") from exc
    if not reviewer_list:
        raise ValueError("at least one reviewer is required")
    reviewer_set: set[str] = set()
    for reviewer in reviewer_list:
        _nonblank(reviewer, 'reviewer_id')
        if reviewer in reviewer_set:
            raise ValueError("duplicate reviewer")
        reviewer_set.add(reviewer)
    if assignment_list is None:
        assigned = {(cid, reviewer) for cid in candidates for reviewer in reviewer_set}
    else:
        assigned = set()
        for item in assignment_list:
            if not isinstance(item, Assignment):
                raise ValueError("assignments must contain only Assignment instances")
            _nonblank(item.candidate_id, 'assignment candidate_id')
            _nonblank(item.reviewer_id, 'assignment reviewer_id')
            pair = (item.candidate_id, item.reviewer_id)
            if item.candidate_id not in candidates or item.reviewer_id not in reviewer_set:
                raise ValueError("assignment references unknown candidate or reviewer")
            if pair in assigned:
                raise ValueError("duplicate assignment")
            assigned.add(pair)
        if not assigned:
            raise ValueError("at least one assignment is required")
    observations: dict[tuple[str, str], Rating] = {}
    for rating in rating_list:
        if not isinstance(rating, Rating):
            raise ValueError("ratings must contain only Rating instances")
        _nonblank(rating.candidate_id, 'rating candidate_id')
        _nonblank(rating.reviewer_id, 'rating reviewer_id')
        pair = (rating.candidate_id, rating.reviewer_id)
        if rating.candidate_id not in candidates or rating.reviewer_id not in reviewer_set:
            raise ValueError("rating references unknown candidate or reviewer")
        if pair not in assigned:
            raise ValueError("rating is not assigned")
        if pair in observations:
            raise ValueError("duplicate rating for candidate and reviewer")
        if rating.label is not None and rating.label not in LABELS:
            raise ValueError("unknown reviewer label")
        _rating_value(rating.legibility, 'legibility')
        _rating_value(rating.similarity, 'similarity')
        observations[pair] = rating
    ids = list(candidates)
    methods = sorted({c['method'] for c in candidates.values()})
    teachers = sorted({c['teacher_id'] for c in candidates.values()})
    def summary(selected: list[str]) -> dict:
        return _summarize(selected, candidates, assigned, observations)
    method_ids = {m: [cid for cid in ids if candidates[cid]['method'] == m] for m in methods}
    teacher_ids = {t: [cid for cid in ids if candidates[cid]['teacher_id'] == t] for t in teachers}
    by_pair = {(c['source_id'], c['method']): cid for cid, c in candidates.items()}
    paired = {}
    for method in methods:
        if method == key['baseline']:
            continue
        all_pairs, pairs_by_teacher = [], defaultdict(list)
        expected_pairs = 0
        expected_by_teacher: Counter[str] = Counter()
        for cid in method_ids[method]:
            candidate = candidates[cid]
            baseline_id = by_pair[(candidate['source_id'], key['baseline'])]
            for reviewer in sorted(reviewer_set):
                if (cid, reviewer) in assigned and (baseline_id, reviewer) in assigned:
                    expected_pairs += 1
                    expected_by_teacher[candidate['teacher_id']] += 1
                proposed = observations.get((cid, reviewer))
                baseline = observations.get((baseline_id, reviewer))
                if proposed is not None and baseline is not None:
                    all_pairs.append((proposed, baseline))
                    pairs_by_teacher[candidate['teacher_id']].append((proposed, baseline))
        paired[method] = {'overall': _paired_summary(all_pairs, expected_pairs),
                          'by_teacher': {t: _paired_summary(pairs_by_teacher[t], expected_by_teacher[t])
                                         for t in teachers}}
    return {
        'schema_version': 1, 'baseline_method': key['baseline'],
        'score_scale': {'minimum': SCORE_MIN, 'maximum': SCORE_MAX},
        'overall': summary(ids),
        'by_method': {m: summary(method_ids[m]) for m in methods},
        'by_teacher': {t: summary(teacher_ids[t]) for t in teachers},
        'by_method_teacher': {m: {t: summary([cid for cid in method_ids[m]
                                              if candidates[cid]['teacher_id'] == t])
                                  for t in teachers} for m in methods},
        'paired_vs_baseline': paired,
        'notes': ['Labels are reviewer judgments, not verified true identities.',
                  'Missing-field counts include unsubmitted assigned rows.',
                  'Inter-rater pairs are not independent or chance-corrected.',
                  'Paired differences use the same source and reviewer; no success threshold is applied.'],
    }
