#!/usr/bin/env python3
"""
End-to-End Pipeline
Sample handwriting image → glyph extraction → TTF font → Classmate PDF lesson note

Usage:
    python scripts/end_to_end_pipeline.py \
        --sample path/to/handwriting_sample.jpg \
        --class SS2 --term "Second Term" --week 2 \
        --output my_lesson.pdf
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ingestion.preprocessor import HandwritingPreprocessor, DEFAULT_SAMPLE_ORDER
from model.font_compiler import FontCompiler
from curriculum.nerdc_schemes import get_lesson
from renderer.pdf_exporter import ClassmatePDFExporter


def find_sample_note(class_level: str, term: str, week: int) -> str:
    samples_dir = ROOT / "samples"
    known = {
        ("SS2", "Second Term", 2): samples_dir / "SS2_Second_Term" / "Week02_Introduction_to_Python.md",
        ("SS1", "First Term", 3): samples_dir / "SS1_First_Term_Week3_Number_Systems.md",
        ("SS3", "First Term", 3): samples_dir / "SS3_First_Term" / "Week03_OOP_Basics.md",
    }
    path = known.get((class_level, term, week))
    if path and path.exists():
        return path.read_text(encoding="utf-8")

    lesson = get_lesson(class_level, term, week)
    if not lesson:
        return f"No lesson found for {class_level} {term} Week {week}"
    return f"""**Class:** {class_level}
**Term:** {term}
**Week:** {week}
**Topic:** {lesson['topic']}

**Official Content**
{lesson['content']}

(Full detailed note not pre-generated – using official scheme content.)
"""


def main():
    parser = argparse.ArgumentParser(description="End-to-end handwriting lesson note pipeline")
    parser.add_argument("--sample", required=True, help="Path to handwriting sample image")
    parser.add_argument("--class", dest="class_level", default="SS2")
    parser.add_argument("--term", default="Second Term")
    parser.add_argument("--week", type=int, default=2)
    parser.add_argument("--output", "-o", default="handwriting_lesson.pdf")
    parser.add_argument("--font-out", default="teacher_handwriting.ttf")
    parser.add_argument("--debug-glyphs", action="store_true")
    args = parser.parse_args()

    sample_path = Path(args.sample)
    if not sample_path.exists():
        print(f"ERROR: Sample image not found: {sample_path}")
        return 1

    print("1. Preprocessing handwriting sample...")
    preprocessor = HandwritingPreprocessor()
    glyphs = preprocessor.process(
        sample_path,
        expected_chars=DEFAULT_SAMPLE_ORDER,
        save_debug=args.debug_glyphs,
        debug_dir="debug_glyphs"
    )
    print(f"   Extracted {len(glyphs)} glyphs")

    print("2. Compiling TrueType font...")
    compiler = FontCompiler()
    font_path = compiler.compile(glyphs, args.font_out, family_name="TeacherHandwriting")
    if not font_path:
        print("   ERROR: Font compilation failed")
        return 1
    print(f"   Font saved to: {font_path}")

    print("3. Loading lesson note...")
    note_text = find_sample_note(args.class_level, args.term, args.week)

    print("4. Rendering Classmate-style PDF (with handwriting font if available)...")
    exporter = ClassmatePDFExporter(font_path=str(font_path) if font_path else None)
    pdf_path = exporter.export_lesson(
        note_text,
        args.output,
        title=f"{args.class_level} {args.term} Week {args.week}"
    )
    print(f"   PDF saved to: {pdf_path}")

    print("\nDone.")
    print(f"  Font : {font_path}")
    print(f"  PDF  : {pdf_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
