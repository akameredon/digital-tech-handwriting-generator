#!/usr/bin/env python3
"""Generate a printable lesson PDF; refuse unsafe handwriting-font generation.

Usage:
    python scripts/end_to_end_pipeline.py --class SS2 --term "Second Term" --week 2

A handwriting recognizer and text-to-glyph alignment provider are not configured.
Passing --sample is therefore rejected instead of producing a falsely labeled font.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from main import build_lesson_payload
from renderer.pdf_exporter import ClassmatePDFExporter


def main(argv=None):
    parser = argparse.ArgumentParser(description="Create a printable Digital Technologies lesson PDF")
    parser.add_argument("--class", dest="class_level", default="SS2", choices=("SS1", "SS2", "SS3"))
    parser.add_argument("--term", default="Second Term", choices=("First Term", "Second Term", "Third Term"))
    parser.add_argument("--week", type=int, default=2, choices=range(1, 14))
    parser.add_argument("--output", "-o", default="lesson.pdf", help="Output PDF path")
    parser.add_argument(
        "--sample",
        help="Deprecated: handwriting conversion is disabled until a real recognizer is configured",
    )
    args = parser.parse_args(argv)

    if args.sample:
        print(
            "ERROR: Handwriting-to-font export is disabled. This project has no configured "
            "handwriting recognizer or text-to-glyph alignment, so the sample was not used. "
            "Omit --sample to create a standard printable PDF.",
            file=sys.stderr,
        )
        return 2

    try:
        payload = build_lesson_payload(args.class_level, args.term, args.week)
        output = Path(args.output).expanduser().resolve()
        pdf_path = ClassmatePDFExporter().export_lesson(
            payload["lesson_note"],
            output,
            title=f"{args.class_level} {args.term} Week {args.week}",
        )
    except Exception as exc:
        print(f"ERROR: Could not create the lesson PDF: {exc}", file=sys.stderr)
        return 1

    print(f"Printable lesson PDF saved to: {pdf_path}")
    if payload["content_status"] == "outline":
        print("Note: this week has a curriculum outline, not a prepared full lesson note.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
