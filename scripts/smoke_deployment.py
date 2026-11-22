#!/usr/bin/env python3
"""Smoke-test a running Lesson Studio deployment using only the Python stdlib."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from email.generator import _make_boundary
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class SmokeCheck:
    name: str
    passed: bool
    detail: str


Fetcher = Callable[[Request, float], tuple[int, dict[str, str], bytes]]


def _default_fetch(request: Request, timeout: float) -> tuple[int, dict[str, str], bytes]:
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - target is operator-supplied
            return response.status, {key.lower(): value for key, value in response.headers.items()}, response.read()
    except HTTPError as exc:
        return exc.code, {key.lower(): value for key, value in exc.headers.items()}, exc.read()
    except URLError as exc:
        raise RuntimeError(f"Could not reach {request.full_url}: {exc.reason}") from exc


def _multipart(fields: dict[str, str]) -> tuple[bytes, str]:
    boundary = _make_boundary()
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode(),
                b"\r\n",
            ]
        )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _json_body(body: bytes) -> dict:
    try:
        value = json.loads(body)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"expected JSON response, got {body[:120]!r}") from exc
    if not isinstance(value, dict):
        raise AssertionError("expected a JSON object")
    return value


def run_smoke(base_url: str, *, timeout: float = 10.0, fetch: Fetcher = _default_fetch) -> list[SmokeCheck]:
    base_url = base_url.rstrip("/")
    checks: list[SmokeCheck] = []

    def check(name: str, action: Callable[[], str]) -> None:
        try:
            checks.append(SmokeCheck(name, True, action()))
        except (AssertionError, RuntimeError, ValueError) as exc:
            checks.append(SmokeCheck(name, False, str(exc)))

    def get(path: str, request_id: str = "smoke-test-7"):
        request = Request(f"{base_url}{path}", headers={"X-Request-ID": request_id})
        return fetch(request, timeout)

    def post_form(path: str, fields: dict[str, str]):
        body, content_type = _multipart(fields)
        request = Request(
            f"{base_url}{path}",
            data=body,
            method="POST",
            headers={"Content-Type": content_type, "X-Request-ID": "smoke-test-7-pdf"},
        )
        return fetch(request, timeout)

    def json_get(path: str) -> tuple[dict, dict[str, str]]:
        status, headers, body = get(path)
        assert status == 200, f"HTTP {status}: {body[:160]!r}"
        return _json_body(body), headers

    def check_health() -> str:
        payload, headers = json_get("/health")
        assert payload.get("status") == "ok", payload
        assert headers.get("x-request-id") == "smoke-test-7", headers
        return "liveness and correlation passed"

    def check_ready() -> str:
        payload, _ = json_get("/ready")
        assert payload.get("status") == "ready", payload
        return f"frontend_built={payload.get('frontend_built')}"

    def check_frontend() -> str:
        status, _, body = get("/")
        assert status == 200, f"HTTP {status}"
        assert b"Digital Technologies Lesson Studio" in body, "frontend marker missing"
        return "frontend marker present"

    def check_topics() -> str:
        status, _, body = get("/topics?class_level=SS2")
        assert status == 200, f"HTTP {status}"
        topics = json.loads(body)
        assert isinstance(topics, list) and len(topics) >= 30, f"unexpected topic count: {len(topics)}"
        return f"{len(topics)} topics"

    def check_lesson() -> str:
        path = "/lesson/SS2/Second%20Term/2"
        payload, _ = json_get(path)
        assert payload.get("content_status") == "prepared", payload
        return "prepared lesson lookup passed"

    def check_pdf() -> str:
        status, headers, body = post_form(
            "/export/lesson-pdf",
            {"class_level": "SS2", "term": "Second Term", "week": "2"},
        )
        assert status == 200, f"HTTP {status}: {body[:160]!r}"
        assert headers.get("content-type", "").startswith("application/pdf"), headers
        assert body.startswith(b"%PDF-"), "PDF signature missing"
        return f"{len(body)} bytes"

    def check_security_headers() -> str:
        status, headers, _ = get("/health")
        assert status == 200, f"HTTP {status}"
        expected = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }
        for name, value in expected.items():
            normalized_name = name.lower()
            assert headers.get(normalized_name) == value, f"{name}={headers.get(normalized_name)!r}"
        return "security headers present"

    check("health", check_health)
    check("readiness", check_ready)
    check("frontend", check_frontend)
    check("topics", check_topics)
    check("lesson", check_lesson)
    check("printable PDF", check_pdf)
    check("security headers", check_security_headers)
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Running deployment base URL")
    parser.add_argument("--timeout", type=float, default=10.0, help="Per-request timeout in seconds")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable results")
    args = parser.parse_args(argv)

    checks = run_smoke(args.base_url, timeout=args.timeout)
    if args.json:
        print(json.dumps([check.__dict__ for check in checks], indent=2))
    else:
        for check in checks:
            print(f"{'PASS' if check.passed else 'FAIL'} {check.name}: {check.detail}")
    return 0 if all(check.passed for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
