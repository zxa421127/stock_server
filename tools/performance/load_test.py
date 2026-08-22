# -*- coding: utf-8 -*-
"""HTTP load test for realistic large market-data responses."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import statistics
import threading
import time
from pathlib import Path

import requests


def _percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * ratio))))
    return ordered[index]


def run(args) -> dict:
    tokens = [line.strip() for line in Path(args.tokens_file).read_text(encoding="utf-8").splitlines() if line.strip()]
    if not tokens:
        raise ValueError("tokens文件为空")
    payload = json.loads(args.json_payload or "{}")
    stop_at = time.monotonic() + args.seconds
    counter = 0
    lock = threading.Lock()
    latencies: list[float] = []
    statuses: dict[str, int] = {}
    bytes_received = 0

    def task(worker_index: int):
        nonlocal counter, bytes_received
        session = requests.Session()
        token = tokens[worker_index % len(tokens)]
        while time.monotonic() < stop_at:
            started = time.monotonic()
            try:
                response = session.request(
                    args.method,
                    args.url,
                    headers={"X-API-Token": token, "Accept-Encoding": "gzip"},
                    json=payload if args.method != "GET" else None,
                    params=payload if args.method == "GET" else None,
                    timeout=args.timeout,
                )
                status = str(response.status_code)
                size = len(response.content)
            except Exception as exc:
                status = type(exc).__name__
                size = 0
            elapsed = (time.monotonic() - started) * 1000
            with lock:
                counter += 1
                bytes_received += size
                latencies.append(elapsed)
                statuses[status] = statuses.get(status, 0) + 1

    started = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(task, index) for index in range(args.concurrency)]
        for future in futures:
            future.result()
    elapsed = max(time.monotonic() - started, 0.001)
    return {
        "url": args.url,
        "method": args.method,
        "concurrency": args.concurrency,
        "elapsed_seconds": round(elapsed, 3),
        "requests": counter,
        "requests_per_second": round(counter / elapsed, 2),
        "received_megabytes": round(bytes_received / 1024 / 1024, 2),
        "network_mbps": round((bytes_received * 8 / 1_000_000) / elapsed, 2),
        "latency_ms": {
            "average": round(statistics.mean(latencies), 2) if latencies else 0,
            "p50": round(_percentile(latencies, 0.50), 2),
            "p95": round(_percentile(latencies, 0.95), 2),
            "p99": round(_percentile(latencies, 0.99), 2),
            "maximum": round(max(latencies), 2) if latencies else 0,
        },
        "statuses": statuses,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="30并发真实大结果HTTP压测")
    parser.add_argument("--url", required=True)
    parser.add_argument("--tokens-file", required=True)
    parser.add_argument("--method", choices=["GET", "POST"], default="POST")
    parser.add_argument("--json-payload", default="{}")
    parser.add_argument("--concurrency", type=int, default=30)
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args()
    result = run(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    bad = sum(count for status, count in result["statuses"].items() if status not in {"200", "204"})
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
