#!/usr/bin/env python3
"""
Backend Concurrency & Load Stress Test Script
---------------------------------------------
Simulates multiple concurrent classroom devices sending simultaneous writes,
inference calls, progress updates, and pack queries to verify database WAL mode,
async execution offloading, file locking, and queue timeout behavior.
"""

import argparse
import asyncio
import time
from typing import Any
import httpx


async def worker_pihub(worker_id: int, base_url: str, num_requests: int) -> list[dict[str, Any]]:
    results = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        device_id = f"stress-device-{worker_id}"
        student_id = f"student-{worker_id}"
        
        auth_token = None
        # Register device first so heartbeat succeeds
        reg = await client.post(
            f"{base_url}/devices",
            json={"device_name": f"Device-{worker_id}", "role": "student", "classroom": "Classroom A", "metadata": {}}
        )
        if reg.status_code in (200, 201):
            body = reg.json()
            device_id = body.get("device_id", device_id)
            auth_token = body.get("auth_token")

        headers = {"x-device-token": auth_token} if auth_token else {}

        for i in range(num_requests):
            start = time.perf_counter()
            try:
                # 1. Heartbeat device
                r1 = await client.post(
                    f"{base_url}/devices/{device_id}/heartbeat",
                    headers=headers,
                    json={"status": "online"}
                )
                
                # 2. Upsert progress (concurrent DB write)
                progress_payload = {
                    "progress_id": f"prog-{worker_id}-{i}",
                    "student_id": student_id,
                    "grade": 8,
                    "subject": "science",
                    "chapter": "force_and_pressure",
                    "score": 85 + (i % 15),
                    "attempts": i + 1,
                    "updated_at": f"2026-08-28T19:{i:02d}:00Z",
                    "topic": "force",
                    "metadata": {"test": True, "worker": worker_id}
                }
                r2 = await client.post(f"{base_url}/progress", json=progress_payload)
                
                # 3. Quiz session creation & advance
                quiz_payload = {
                    "quiz_session_id": f"quiz-{worker_id}-{i}",
                    "student_id": student_id,
                    "active_quiz_id": "q101",
                    "grade": 8,
                    "subject": "science",
                    "questions": [{"id": 1, "text": "What is pressure?"}],
                    "total_questions": 1
                }
                r3 = await client.post(f"{base_url}/quiz-sessions", json=quiz_payload)

                elapsed = (time.perf_counter() - start) * 1000
                statuses = [r1.status_code, r2.status_code, r3.status_code]
                success = all(s in (200, 201) for s in statuses)
                results.append({
                    "worker_id": worker_id,
                    "step": i,
                    "success": success,
                    "elapsed_ms": elapsed,
                    "statuses": statuses,
                    "error": None
                })
            except Exception as exc:
                elapsed = (time.perf_counter() - start) * 1000
                results.append({
                    "worker_id": worker_id,
                    "step": i,
                    "success": False,
                    "elapsed_ms": elapsed,
                    "statuses": [],
                    "error": str(exc)
                })
            await asyncio.sleep(0.05)
    return results


async def worker_classroom(worker_id: int, base_url: str, num_requests: int) -> list[dict[str, Any]]:
    results = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for i in range(num_requests):
            start = time.perf_counter()
            try:
                payload = {
                    "teacher_id": f"teacher-{worker_id}",
                    "title": f"Classroom Session {worker_id}-{i}",
                    "active": True
                }
                r = await client.post(f"{base_url}/classroom/sessions", json=payload)
                elapsed = (time.perf_counter() - start) * 1000
                results.append({
                    "worker_id": worker_id,
                    "step": i,
                    "success": r.status_code in (200, 201),
                    "elapsed_ms": elapsed,
                    "statuses": [r.status_code],
                    "error": None if r.status_code in (200, 201) else r.text[:100]
                })
            except Exception as exc:
                elapsed = (time.perf_counter() - start) * 1000
                results.append({
                    "worker_id": worker_id,
                    "step": i,
                    "success": False,
                    "elapsed_ms": elapsed,
                    "statuses": [],
                    "error": str(exc)
                })
            await asyncio.sleep(0.05)
    return results


async def worker_inference(worker_id: int, base_url: str, num_requests: int) -> list[dict[str, Any]]:
    results = []
    async with httpx.AsyncClient(timeout=35.0) as client:
        for i in range(num_requests):
            start = time.perf_counter()
            try:
                payload = {
                    "question": f"Explain gravity simply for grade 8 student (test {worker_id}-{i})",
                    "grade": 8,
                    "subject": "science",
                    "chapter": "gravitation"
                }
                r = await client.post(f"{base_url}/ai/tutor", json=payload)
                elapsed = (time.perf_counter() - start) * 1000
                # 200/201 (success) or 530/429 (graceful busy response) are acceptable handled responses
                valid = r.status_code in (200, 201, 429, 530)
                results.append({
                    "worker_id": worker_id,
                    "step": i,
                    "success": valid,
                    "elapsed_ms": elapsed,
                    "statuses": [r.status_code],
                    "error": None if valid else r.text[:100]
                })
            except Exception as exc:
                elapsed = (time.perf_counter() - start) * 1000
                results.append({
                    "worker_id": worker_id,
                    "step": i,
                    "success": False,
                    "elapsed_ms": elapsed,
                    "statuses": [],
                    "error": str(exc)
                })
            await asyncio.sleep(0.1)
    return results


async def run_stress_test(concurrency: int, requests_per_worker: int):
    print(f"=== STARTING CONCURRENCY STRESS TEST ===")
    print(f"Workers (Concurrency): {concurrency}")
    print(f"Requests per worker:   {requests_per_worker}")
    print(f"Total simulated clients: {concurrency * 3}")

    start_total = time.perf_counter()

    tasks = []
    # Launch concurrent PiHub DB workers
    for w in range(concurrency):
        tasks.append(worker_pihub(w, "http://127.0.0.1:8020", requests_per_worker))
    # Launch concurrent Classroom DB workers
    for w in range(concurrency):
        tasks.append(worker_classroom(w, "http://127.0.0.1:8040", requests_per_worker))
    # Launch concurrent Inference workers
    for w in range(concurrency):
        tasks.append(worker_inference(w, "http://127.0.0.1:8010", requests_per_worker))

    worker_outputs = await asyncio.gather(*tasks, return_exceptions=True)
    total_elapsed = time.perf_counter() - start_total

    all_results = []
    for output in worker_outputs:
        if isinstance(output, list):
            all_results.extend(output)
        elif isinstance(output, Exception):
            print(f"[ERROR] Worker task failed: {output}")

    total_ops = len(all_results)
    successes = [r for r in all_results if r["success"]]
    failures = [r for r in all_results if not r["success"]]
    latencies = [r["elapsed_ms"] for r in all_results]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

    print("\n=== CONCURRENCY STRESS TEST RESULTS ===")
    print(f"Total Operations Attempted : {total_ops}")
    print(f"Successful Operations       : {len(successes)} ({len(successes)/max(1, total_ops)*100:.1f}%)")
    print(f"Failed Operations           : {len(failures)}")
    print(f"Total Duration              : {total_elapsed:.2f} seconds")
    print(f"Average Latency per Op      : {avg_latency:.2f} ms")
    print(f"Throughput                  : {total_ops / max(0.001, total_elapsed):.2f} ops/sec")

    if failures:
        print("\nFirst 5 Failure Samples:")
        for f in failures[:5]:
            print(f"  Worker {f['worker_id']} Step {f['step']}: Error={f['error']} Statuses={f['statuses']}")

    # Check for "database is locked" errors in failures
    db_lock_errors = [f for f in failures if f['error'] and "database is locked" in f['error'].lower()]
    print(f"\nSQLite 'database is locked' errors encountered: {len(db_lock_errors)}")

    if len(failures) == 0 and len(db_lock_errors) == 0:
        print("\nPASSED: 100% success rate with ZERO database lock errors!")
    elif len(db_lock_errors) == 0:
        print("\nPASSED: Zero database lock errors encountered.")
    else:
        print("\nFAILED: Database locking errors were observed!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=10, help="Number of concurrent workers per service")
    parser.add_argument("--requests", type=int, default=5, help="Number of requests per worker")
    args = parser.parse_args()

    asyncio.run(run_stress_test(args.concurrency, args.requests))
