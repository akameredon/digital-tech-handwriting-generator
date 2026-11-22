#!/usr/bin/env python3
"""Measure core HTTP runtime behavior against a running Lesson Studio service."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
import json
import statistics
import time
from urllib.request import Request

from scripts.smoke_deployment import _default_fetch, _multipart


@dataclass(frozen=True)
class RequestSample:
    latency_ms: float
    status: int
    response_bytes: int
    error: str | None = None


@dataclass(frozen=True)
class EndpointBudget:
    name: str
    path: str
    method: str = "GET"
    max_p95_ms: float = 2000.0


@dataclass(frozen=True)
class EndpointReport:
    name: str
    path: str
    method: str
    requests: int
    successes: int
    errors: int
    mean_ms: float
    p50_ms: float
    p95_ms: float
    max_ms: float
    mean_response_bytes: float
    passed: bool
    failures: tuple[str, ...]


DEFAULT_BUDGETS = (
    EndpointBudget("health", "/health"),
    EndpointBudget("readiness", "/ready"),
    EndpointBudget("topics", "/topics?class_level=SS2"),
    EndpointBudget("lesson", "/lesson/SS2/Second%20Term/2"),
    EndpointBudget("printable PDF", "/export/lesson-pdf", "POST"),
)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * percentile)))
    return ordered[index]


def _request(base_url: str, budget: EndpointBudget, timeout: float, sequence: int) -> RequestSample:
    url = f"{base_url.rstrip('/')}{budget.path}"
    headers = {"X-Request-ID": f"runtime-bench-{sequence}"}
    data = None
    if budget.method == "POST":
        data, content_type = _multipart({"class_level": "SS2", "term": "Second Term", "week": "2"})
        headers["Content-Type"] = content_type
    started = time.perf_counter()
    try:
        response_status, _, body = _default_fetch(
            Request(url, data=data, method=budget.method, headers=headers), timeout
        )
        return RequestSample(
            latency_ms=(time.perf_counter() - started) * 1000,
            status=response_status,
            response_bytes=len(body),
            error=None if response_status == 200 else f"HTTP {response_status}",
        )
    except Exception as exc:  # pragma: no cover - exercised against a live deployment
        return RequestSample(
            latency_ms=(time.perf_counter() - started) * 1000,
            status=0,
            response_bytes=0,
            error=str(exc),
        )


def benchmark_runtime(
    base_url: str,
    *,
    requests_per_endpoint: int = 5,
    concurrency: int = 2,
    timeout: float = 10.0,
    budgets: tuple[EndpointBudget, ...] = DEFAULT_BUDGETS,
) -> list[EndpointReport]:
    if requests_per_endpoint < 1:
        raise ValueError("requests_per_endpoint must be at least 1")
    if concurrency < 1:
        raise ValueError("concurrency must be at least 1")

    reports: list[EndpointReport] = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        for budget in budgets:
            futures = [
                executor.submit(_request, base_url, budget, timeout, index)
                for index in range(requests_per_endpoint)
            ]
            samples = [future.result() for future in as_completed(futures)]
            latencies = [sample.latency_ms for sample in samples]
            successes = [sample for sample in samples if sample.error is None]
            failures = tuple(sorted({sample.error for sample in samples if sample.error}))
            p95_ms = _percentile(latencies, 0.95)
            passed = bool(samples) and not failures and p95_ms <= budget.max_p95_ms
            budget_failures = list(failures)
            if p95_ms > budget.max_p95_ms:
                budget_failures.append(
                    f"p95 {p95_ms:.1f} ms exceeds {budget.max_p95_ms:.1f} ms budget"
                )
            reports.append(
                EndpointReport(
                    name=budget.name,
                    path=budget.path,
                    method=budget.method,
                    requests=len(samples),
                    successes=len(successes),
                    errors=len(samples) - len(successes),
                    mean_ms=round(statistics.fmean(latencies), 3) if latencies else 0.0,
                    p50_ms=round(_percentile(latencies, 0.50), 3),
                    p95_ms=round(p95_ms, 3),
                    max_ms=round(max(latencies), 3) if latencies else 0.0,
                    mean_response_bytes=round(
                        statistics.fmean(sample.response_bytes for sample in samples), 1
                    ) if samples else 0.0,
                    passed=passed,
                    failures=tuple(budget_failures),
                )
            )
    return reports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--requests", type=int, default=5, dest="requests_per_endpoint")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--p95-budget-ms", type=float, default=2000.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    budgets = tuple(
        EndpointBudget(item.name, item.path, item.method, args.p95_budget_ms)
        for item in DEFAULT_BUDGETS
    )
    reports = benchmark_runtime(
        args.base_url,
        requests_per_endpoint=args.requests_per_endpoint,
        concurrency=args.concurrency,
        timeout=args.timeout,
        budgets=budgets,
    )
    if args.json:
        print(json.dumps([asdict(report) for report in reports], indent=2))
    else:
        for report in reports:
            state = "PASS" if report.passed else "FAIL"
            print(
                f"{state} {report.name}: p50={report.p50_ms:.1f}ms "
                f"p95={report.p95_ms:.1f}ms errors={report.errors} "
                f"mean_bytes={report.mean_response_bytes:.0f}"
            )
            for failure in report.failures:
                print(f"  - {failure}")
    return 0 if all(report.passed for report in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
