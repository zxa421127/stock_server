# -*- coding: utf-8 -*-
"""Small paced HTTP load test for deployment verification.

Examples:
python -m tools.load_test --url http://127.0.0.1:8898/ping --concurrency 30 --rps 400 --seconds 20
python -m tools.load_test --url http://127.0.0.1:8898/api/v1/market/providers \
  --tokens-file tokens.txt --concurrency 30 --rps 400 --seconds 60
"""
from __future__ import annotations

import argparse
import concurrent.futures
import statistics
import threading
import time
from dataclasses import dataclass

import requests


@dataclass(slots=True)
class Result:
    ok: bool
    latency_ms: float
    status: int
    started_at: float
    finished_at: float


_thread_local = threading.local()


def _session() -> requests.Session:
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=0)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        _thread_local.session = session
    return session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--concurrency", type=int, default=30)
    parser.add_argument("--rps", type=int, default=400)
    parser.add_argument("--seconds", type=int, default=20)
    parser.add_argument("--token", default="")
    parser.add_argument("--tokens-file", default="", help="one API token per line; requests rotate across tokens")
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()

    tokens: list[str] = []
    if args.tokens_file:
        with open(args.tokens_file, "r", encoding="utf-8") as handle:
            tokens = [line.strip() for line in handle if line.strip()]
    if not tokens and args.token:
        tokens = [args.token]

    target_rps = max(1, args.rps)
    total_target = target_rps * max(1, args.seconds)
    interval = 1.0 / target_rps
    test_started = time.monotonic()

    def one_request(request_index: int) -> Result:
        started = time.monotonic()
        try:
            headers = {"X-API-Token": tokens[request_index % len(tokens)]} if tokens else {}
            response = _session().get(args.url, headers=headers, timeout=args.timeout)
            finished = time.monotonic()
            return Result(response.status_code < 400, (finished - started) * 1000, response.status_code, started, finished)
        except Exception:
            finished = time.monotonic()
            return Result(False, (finished - started) * 1000, 0, started, finished)

    results: list[Result] = []
    futures: list[concurrent.futures.Future[Result]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as executor:
        # Submit at the requested pace. This avoids counting a large up-front
        # Future creation pause as server processing time.
        for request_index in range(total_target):
            scheduled_at = test_started + request_index * interval
            delay = scheduled_at - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            futures.append(executor.submit(one_request, request_index))

        submission_finished = time.monotonic()
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    test_finished = time.monotonic()
    latencies = sorted(item.latency_ms for item in results)
    ok_count = sum(item.ok for item in results)
    first_started = min((item.started_at for item in results), default=test_started)
    last_started = max((item.started_at for item in results), default=test_started)
    last_finished = max((item.finished_at for item in results), default=test_finished)
    request_start_window = max(interval, last_started - first_started + interval)
    completion_window = max(interval, last_finished - first_started)

    def percentile(p: float) -> float:
        if not latencies:
            return 0.0
        index = min(len(latencies) - 1, int((len(latencies) - 1) * p))
        return latencies[index]

    status_counts: dict[int, int] = {}
    for item in results:
        status_counts[item.status] = status_counts.get(item.status, 0) + 1

    print(f"requests={len(results)} success={ok_count} failed={len(results)-ok_count}")
    print(
        f"target_rps={target_rps} submitted_rps={len(results)/request_start_window:.2f} "
        f"completed_rps={len(results)/completion_window:.2f}"
    )
    print(
        f"submit_elapsed={submission_finished-test_started:.2f}s "
        f"completion_elapsed={test_finished-test_started:.2f}s"
    )
    if latencies:
        print(
            f"latency_ms avg={statistics.mean(latencies):.2f} "
            f"p50={percentile(0.50):.2f} p95={percentile(0.95):.2f} "
            f"p99={percentile(0.99):.2f} max={max(latencies):.2f}"
        )
    print("status_counts=" + ",".join(f"{status}:{count}" for status, count in sorted(status_counts.items())))


if __name__ == "__main__":
    main()
