#!/usr/bin/env python3
"""Local, experimental worksheet-skeleton PDF; never a font or handwriting proof."""
from __future__ import annotations

import argparse
from io import BytesIO
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from curriculum.sample_notes import prepared_lesson_index
from ingestion.calibration_sheet import MAX_IMAGE_BYTES, extract_calibration_glyphs
from model.teacher_ink import profile_from_confirmed_crops
from renderer.teacher_stroke_generation import RenderOptions, TeacherStrokeGenerator
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

# The renderer also has stricter cumulative trajectory-point and pixel budgets.
MAX_TEXT_BYTES = 40_000
MAX_TEXT_CHARACTERS = 10_000
MAX_CURRICULUM_FILES = 256
MAX_PAGES = 8
PAGE_WIDTH = 1240
PAGE_HEIGHT = 1754
LAYOUT_CHARS = " \t\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="EXPERIMENTAL local fixed-worksheet skeleton geometry to image-only A4 PDF (no font or ML).",
        allow_abbrev=False,
    )
    parser.add_argument("--worksheet", required=True, type=Path, help="Local JPG/PNG of the generated fixed-cell worksheet")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text-file", type=Path, help="Exact UTF-8 text file (not normalized or converted)")
    source.add_argument("--class", dest="class_level", choices=("SS1", "SS2", "SS3"), help="Prepared curriculum lesson class")
    parser.add_argument("--term", choices=("First Term", "Second Term", "Third Term"))
    parser.add_argument("--week", type=int, choices=range(1, 14), metavar="1..13")
    parser.add_argument("--output", "-o", required=True, type=Path, help="New PDF path; parent must already exist")
    parser.add_argument("--report", type=Path, help="Optional new metadata-light JSON report path")
    parser.add_argument("--seed", type=int, default=0, help="Deterministic layout seed (signed 64-bit integer)")
    parser.add_argument("--confirm-labels", action="store_true", required=True,
                        help="Confirm that worksheet cell labels match the supplied samples")
    parser.add_argument("--acknowledge-experimental", action="store_true", required=True,
                        help="Acknowledge the experimental and image-only limitations")
    return parser


def _validate_arguments(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.text_file is not None and (args.term is not None or args.week is not None):
        parser.error("--term and --week are only valid with --class; do not mix text and lesson sources")
    if args.class_level is not None and (args.term is None or args.week is None):
        parser.error("--class requires both --term and --week")
    if not -(2**63) <= args.seed < 2**63:
        parser.error("--seed must be a signed 64-bit integer")
    if args.output.suffix.lower() != ".pdf":
        parser.error("--output must have a .pdf extension")
    if args.report is not None and args.report.suffix.lower() != ".json":
        parser.error("--report must have a .json extension")


def _read_regular_file(path: Path, limit: int, description: str) -> bytes:
    """Read at most limit+1 bytes, rejecting devices/FIFOs and growing files."""
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(path, flags)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise ValueError(f"{description} must be a regular local file")
            if info.st_size > limit:
                raise ValueError(f"{description} exceeds the {limit}-byte limit")
            data = stream.read(limit + 1)
    except OSError as exc:
        raise ValueError(f"Cannot read {description}: {exc.strerror or 'file error'}") from exc
    if len(data) > limit:
        raise ValueError(f"{description} exceeds the {limit}-byte limit")
    if not data:
        raise ValueError(f"{description} is empty")
    return data


def _source_text(args: argparse.Namespace) -> tuple[str, str]:
    if args.text_file is not None:
        path, kind = args.text_file, "text_file"
    else:
        # Only the repository's existing uniquely indexed, curriculum-matched
        # prepared notes are eligible. Do not invent or silently use an outline.
        # The existing index reads its local Markdown files while discovering
        # their metadata; bound those files before handing them to that API.
        root = ROOT / "samples"
        if not root.is_dir():
            raise ValueError("The local prepared-lesson directory is unavailable")
        for count, candidate in enumerate(root.rglob("*.md"), start=1):
            if count > MAX_CURRICULUM_FILES:
                raise ValueError("The local prepared-lesson index exceeds the file-count limit")
            try:
                info = candidate.stat()
            except OSError as exc:
                raise ValueError("Cannot inspect a local prepared-lesson file") from exc
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_TEXT_BYTES:
                raise ValueError("A local prepared-lesson file is nonregular or exceeds the size limit")
        path = prepared_lesson_index(root).get((args.class_level, args.term, args.week))
        if path is None:
            raise ValueError("No curriculum-matched prepared lesson exists for that class, term and week")
        kind = "prepared_lesson"
    raw = _read_regular_file(path, MAX_TEXT_BYTES, "Text source")
    try:
        text = raw.decode("utf-8")  # no newline conversion, BOM removal or normalization
    except UnicodeDecodeError as exc:
        raise ValueError(f"Text source must be UTF-8 (invalid byte at offset {exc.start})") from exc
    if len(text) > MAX_TEXT_CHARACTERS:
        raise ValueError(f"Text source exceeds the {MAX_TEXT_CHARACTERS}-code-point limit")
    if not any(ch not in LAYOUT_CHARS for ch in text):
        raise ValueError("Text source is blank (only space, tab or LF)")
    return text, kind


def _check_destinations(output: Path, report: Path | None) -> None:
    destinations = [output] + ([report] if report is not None else [])
    if len(destinations) == 2 and destinations[0].resolve() == destinations[1].resolve():
        raise ValueError("PDF and report destinations must be different")
    for path in destinations:
        if not path.parent.is_dir():
            raise ValueError("Each destination parent directory must already exist")
        # lexists also rejects broken symlinks. The later hard-link operation is
        # the actual atomic no-overwrite check, not this advisory precheck.
        if os.path.lexists(path):
            raise ValueError("A destination already exists; refusing to overwrite")


def _check_accounting(text: str, result) -> dict:
    """Require a one-to-one mapping of all non-layout source code points."""
    expected = [(i, ch) for i, ch in enumerate(text) if ch not in LAYOUT_CHARS]
    actual = [(p.offset, p.character) for p in result.placements]
    if actual != expected:
        raise ValueError("Renderer source placement accounting failed; no output was created")
    if not result.pages or len(result.pages) > MAX_PAGES:
        raise ValueError("Renderer returned an invalid number of pages")
    if result.joins:
        raise ValueError("Unexpected heuristic joins in strict experimental rendering")
    left, top, right, bottom = result.drawable_bounds
    page_offsets = [[] for _ in result.pages]
    for page in result.pages:
        if page.size != (PAGE_WIDTH, PAGE_HEIGHT):
            raise ValueError("Renderer returned unexpected page dimensions")
    for placement in result.placements:
        if not 0 <= placement.page_index < len(result.pages) or placement.line_index < 0:
            raise ValueError("Renderer returned an invalid placement location")
        l, t, r, b = placement.bounds
        if not (0 <= left <= l <= r <= right < PAGE_WIDTH
                and 0 <= top <= t <= b <= bottom < PAGE_HEIGHT):
            raise ValueError("Renderer placement is outside the drawable page bounds")
        page_offsets[placement.page_index].append(placement.offset)
    layout_offsets = {
        "space": [i for i, ch in enumerate(text) if ch == " "],
        "tab": [i for i, ch in enumerate(text) if ch == "\t"],
        "lf": [i for i, ch in enumerate(text) if ch == "\n"],
    }
    return {"source_codepoints": len(text), "placed_glyphs": len(actual),
            "layout_codepoints": sum(map(len, layout_offsets.values())),
            "placement_offsets_by_page": page_offsets, "layout_offsets": layout_offsets}


def _pdf_bytes(pages) -> bytes:
    # ReportLab embeds each complete raster page, centered and fitted without
    # resampling, stretching or clipping, on an actual A4 portrait media box.
    out = BytesIO()
    pdf = canvas.Canvas(out, pagesize=A4, pageCompression=1)
    pdf.setTitle("Experimental trajectory PDF")
    pdf.setAuthor("")
    pdf.setSubject("")
    pdf.setCreator("Experimental local worksheet prototype")
    for page in pages:
        scale = min(A4[0] / page.width, A4[1] / page.height)
        width, height = page.width * scale, page.height * scale
        pdf.drawImage(ImageReader(page), (A4[0] - width) / 2, (A4[1] - height) / 2,
                      width=width, height=height, preserveAspectRatio=True, mask=None)
        pdf.showPage()
    pdf.save()
    return out.getvalue()


def _publish_new_files(files: list[tuple[Path, bytes]]) -> None:
    """Publish with atomic create-if-absent; roll back our links on any failure.

    Multi-file creation cannot be simultaneous. The PDF is linked last; until
    then a report may briefly be visible, and is removed if publication fails.
    Temp files are private, on the destination filesystems, and always removed.
    """
    temps: list[tuple[Path, str]] = []
    success = False
    try:
        for path, data in files:
            fd, temporary = tempfile.mkstemp(prefix=".experimental-writer-", dir=path.parent)
            temps.append((path, temporary))
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        for path, temporary in temps:
            os.link(temporary, path)  # atomic; fails if destination exists, including symlinks
        success = True
    finally:
        if not success:
            # Check every temporary, including a link made immediately before
            # an interruption. Never remove an unrelated competing file.
            for path, temporary in reversed(temps):
                try:
                    # Do not remove a destination a different process replaced.
                    if os.path.samestat(os.stat(path, follow_symlinks=False), os.stat(temporary)):
                        os.unlink(path)
                except FileNotFoundError:
                    pass
        for _, temporary in temps:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def main(argv=None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    _validate_arguments(parser, args)
    print("WARNING: EXPERIMENTAL fixed-worksheet skeleton prototype, not authentic handwriting "
          "or proof of similarity. The PDF is image-only: text is not selectable or accessible.", file=sys.stderr)
    try:
        _check_destinations(args.output, args.report)
        text, source_kind = _source_text(args)
        worksheet = _read_regular_file(args.worksheet, MAX_IMAGE_BYTES, "Worksheet")
        glyphs, missing = extract_calibration_glyphs(worksheet)
        profile, profile_report = profile_from_confirmed_crops(
            glyphs, name="local experimental worksheet", labels_confirmed=args.confirm_labels
        )
        options = RenderOptions(page_width=PAGE_WIDTH, page_height=PAGE_HEIGHT, margin=75,
                                line_height=52, em_size=34, letter_spacing=5,
                                space_advance=16, stroke_width=2, max_pages=MAX_PAGES,
                                max_characters=MAX_TEXT_CHARACTERS, enable_heuristic_joins=False)
        result = TeacherStrokeGenerator(profile, options=options).render(text, seed=args.seed)
        accounting = _check_accounting(text, result)
        ambiguity_count = sum(bool(item["ambiguous_structure"])
                              for item in profile_report["glyphs"].values())
        if ambiguity_count:
            print("WARNING: Some sampled geometry is ambiguous or may touch a crop edge; review output manually.",
                  file=sys.stderr)
        for warning in result.warnings:
            print(f"WARNING: {warning}", file=sys.stderr)
        pdf_data = _pdf_bytes(result.pages)
        files: list[tuple[Path, bytes]] = []
        if args.report is not None:
            report = {
                "schema_version": 1, "experimental": True, "image_only": True,
                "source_kind": source_kind, "page_count": len(result.pages),
                "page_pixels": [PAGE_WIDTH, PAGE_HEIGHT], "paper": "A4 portrait",
                "worksheet_available_glyphs": len(glyphs), "worksheet_missing_glyphs": len(missing),
                "ambiguous_glyphs": ambiguity_count, "synthetic_joins": len(result.joins),
                "accounting": accounting,
            }
            files.append((args.report, (json.dumps(report, indent=2) + "\n").encode("utf-8")))
        files.append((args.output, pdf_data))  # publish PDF last
        _publish_new_files(files)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Created PDF: {args.output.name!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
