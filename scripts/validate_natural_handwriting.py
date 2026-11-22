"""Run the natural handwriting validation gates from a JSONL manifest."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from model.htr_providers import kraken_from_environment, trocr_from_environment
from model.natural_handwriting_validation import load_cases, validate_pages


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="JSONL manifest with image_path, reference_text, and real_data")
    parser.add_argument("--provider", choices=("trocr", "kraken"), default="trocr")
    parser.add_argument("--max-cer", type=float, default=0.10)
    parser.add_argument("--max-wer", type=float, default=0.20)
    parser.add_argument("--output", type=Path, help="Optional JSON report destination")
    args = parser.parse_args(argv)

    provider = kraken_from_environment() if args.provider == "kraken" else trocr_from_environment()
    report = validate_pages(provider, load_cases(args.manifest), max_cer=args.max_cer, max_wer=args.max_wer)
    payload = json.dumps(report.public_dict(), indent=2)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    if not report.real_data:
        print("Validation did not use an all-real labelled manifest; this is not a production acceptance result.")
    return 0 if report.passed and report.real_data else 2


if __name__ == "__main__":
    raise SystemExit(main())
