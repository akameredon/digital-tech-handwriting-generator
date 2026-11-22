#!/usr/bin/env python3
"""Benchmark a configured local HTR provider against a JSONL manifest."""
from __future__ import annotations

import argparse
import json

from model.htr_benchmark import benchmark_provider, load_cases
from model.htr_providers import TrOCRConfig, TrOCRProvider


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Measure local HTR accuracy, latency, confidence review rate, and memory."
    )
    parser.add_argument("manifest", help="JSONL file containing image_path, reference, and optional case_id.")
    parser.add_argument("--model", default="microsoft/trocr-small-handwritten")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--allow-download", action="store_true", help="Allow Transformers to download the model.")
    parser.add_argument("--threads", type=int, default=None)
    parser.add_argument("--max-new-tokens", type=int, default=128)
    parser.add_argument("--output", help="Optional JSON report path.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    provider = TrOCRProvider(TrOCRConfig(
        model_id=args.model,
        device=args.device,
        local_files_only=not args.allow_download,
        num_threads=args.threads,
        max_new_tokens=args.max_new_tokens,
    ))
    report = benchmark_provider(provider, load_cases(args.manifest))
    payload = report.public_dict()
    serialized = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(serialized + "\n")
    else:
        print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
