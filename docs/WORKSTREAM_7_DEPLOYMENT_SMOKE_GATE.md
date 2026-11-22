# Workstream 7 — deployment smoke gate

## Purpose

Workstream 7 turns the core launch checks into one repeatable, dependency-free command. It is intended for a local preview, a CI container, or a deployment URL after the service starts.

```bash
python scripts/smoke_deployment.py --base-url http://127.0.0.1:8000
```

Use `--json` for an artifact that can be attached to a release record:

```bash
python scripts/smoke_deployment.py --base-url https://preview.example.invalid --json > smoke-report.json
```

## Checks

The command verifies liveness, readiness, request correlation, frontend serving, curriculum topics, a prepared lesson lookup, printable PDF export, PDF content type/signature, and the response security headers. It exits `0` only when every check passes.

GitHub Actions runs the same command against the built container, so preview verification does not depend on a manually copied curl sequence.

## Boundaries

A smoke pass proves that the service is reachable and the core HTTP path is functioning. It does not prove real teacher-handwriting accuracy, accessibility conformance, sustained latency, memory limits, rollback execution, or production approval. Those remain separate release gates and must be recorded against the target deployment environment.
