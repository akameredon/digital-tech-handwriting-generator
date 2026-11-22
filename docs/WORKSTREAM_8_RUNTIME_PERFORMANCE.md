# Workstream 8 — runtime performance gate

## Purpose

Workstream 8 adds a repeatable, dependency-free benchmark for the core deployment surface. It measures latency, p50/p95, errors, maximum latency, response size, and pass/fail status for liveness, readiness, topics, lesson lookup, and printable PDF export.

Run it against a local or preview service:

```bash
python scripts/benchmark_runtime.py \
  --base-url http://127.0.0.1:8000 \
  --requests 5 \
  --concurrency 2 \
  --p95-budget-ms 2000
```

Use `--json` to save a release artifact. The command exits nonzero when an endpoint returns an error or exceeds the configured p95 budget.

## Interpretation

The benchmark is intentionally conservative and configurable. Run it in the target deployment environment with safe data before setting a release decision. Local sandbox timings are engineering evidence only; they do not prove free-tier memory behavior, sustained throughput, cold-start latency, or real teacher workflow performance.

This workstream does not download an HTR model, call a paid service, change hosting configuration, or claim production acceptance for natural handwriting recognition.
