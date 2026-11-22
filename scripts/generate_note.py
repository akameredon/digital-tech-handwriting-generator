#!/usr/bin/env python3
"""
CLI tool to generate / retrieve lesson notes for Digital Technologies.
Usage:
    python scripts/generate_note.py --class SS2 --term "Second Term" --week 2
    python scripts/generate_note.py --list SS1
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from curriculum.nerdc_schemes import get_lesson, list_all_topics, NERDC_DIGITAL_TECHNOLOGIES
from curriculum.prompt_engine import build_prompt
from curriculum.sample_notes import get_prepared_lesson


def main():
    parser = argparse.ArgumentParser(description="Ink Flow Handwriting Studio — Digital Technologies lesson notes")
    parser.add_argument("--class", dest="class_level", help="SS1, SS2 or SS3")
    parser.add_argument("--term", help='e.g. "First Term", "Second Term", "Third Term"')
    parser.add_argument("--week", type=int, help="Week number")
    parser.add_argument("--list", dest="list_class", help="List all topics for a class")
    parser.add_argument("--prompt", action="store_true", help="Show the LLM generation prompt")
    args = parser.parse_args()

    if args.list_class:
        topics = list_all_topics(args.list_class)
        print(f"\n=== {args.list_class} Digital Technologies Topics ===\n")
        current_term = None
        for t in topics:
            if t["term"] != current_term:
                current_term = t["term"]
                print(f"\n--- {current_term} ---")
            print(f"  Week {t['week']:2d}: {t['topic']}")
        return

    if not (args.class_level and args.term and args.week):
        parser.print_help()
        print("\nExample:")
        print('  python scripts/generate_note.py --class SS2 --term "Second Term" --week 2')
        return

    lesson = get_lesson(args.class_level, args.term, args.week)
    if not lesson:
        print(f"ERROR: No lesson found for {args.class_level} / {args.term} / Week {args.week}")
        return

    if args.prompt:
        prompt = build_prompt(args.class_level, args.term, args.week)
        print(prompt)
        return

    prepared_note = get_prepared_lesson(args.class_level, args.term, args.week)
    if prepared_note is not None:
        print(prepared_note)
    else:
        print(f"**Class:** {args.class_level}")
        print(f"**Term:** {args.term}")
        print(f"**Week:** {args.week}")
        print(f"**Topic:** {lesson['topic']}")
        print()
        print("**Official NERDC Content**")
        print(lesson["content"])
        print()
        print("(Full detailed lesson note not yet pre-generated for this week.)")
        print("Use --prompt to get a ready LLM prompt to generate it.")


if __name__ == "__main__":
    main()
