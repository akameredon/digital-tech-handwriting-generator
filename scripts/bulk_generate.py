#!/usr/bin/env python3
"""
Bulk generate lesson note prompts or list all content weeks for a class/term.
Useful when preparing a full term at once.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from curriculum.nerdc_schemes import NERDC_DIGITAL_TECHNOLOGIES, get_lesson
from curriculum.prompt_engine import build_prompt
from curriculum.validator import is_exam_or_break_week


def main():
    parser = argparse.ArgumentParser(description="Bulk lesson note helper")
    parser.add_argument("--class", dest="class_level", required=True, help="SS1, SS2 or SS3")
    parser.add_argument("--term", required=True, help='e.g. "Second Term"')
    parser.add_argument("--prompts", action="store_true", help="Print LLM prompts for content weeks")
    parser.add_argument("--list", action="store_true", help="List all weeks in the term")
    args = parser.parse_args()

    if args.class_level not in NERDC_DIGITAL_TECHNOLOGIES:
        print("Invalid class. Use SS1, SS2 or SS3")
        return

    if args.term not in NERDC_DIGITAL_TECHNOLOGIES[args.class_level]:
        print(f"Invalid term for {args.class_level}")
        print("Available:", list(NERDC_DIGITAL_TECHNOLOGIES[args.class_level].keys()))
        return

    weeks = NERDC_DIGITAL_TECHNOLOGIES[args.class_level][args.term]

    if args.list or not args.prompts:
        print(f"\n{args.class_level} – {args.term}\n" + "=" * 40)
        for item in weeks:
            flag = " [EXAM/BREAK]" if is_exam_or_break_week(item["topic"]) else ""
            print(f"Week {item['week']:2d}: {item['topic']}{flag}")
        return

    if args.prompts:
        print(f"\nLLM Prompts for {args.class_level} – {args.term}\n")
        for item in weeks:
            if is_exam_or_break_week(item["topic"]):
                continue
            prompt = build_prompt(args.class_level, args.term, item["week"])
            print("=" * 60)
            print(f"WEEK {item['week']}: {item['topic']}")
            print("=" * 60)
            print(prompt)
            print("\n\n")


if __name__ == "__main__":
    main()
