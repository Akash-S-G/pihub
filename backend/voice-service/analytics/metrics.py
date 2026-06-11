from __future__ import annotations

import time
from collections import defaultdict
from contextlib import contextmanager
from typing import Iterator


class VoiceMetrics:
    def __init__(self) -> None:
        self.counters: dict[str, int] = defaultdict(int)
        self.latencies: dict[str, list[float]] = defaultdict(list)

    def increment(self, name: str, value: int = 1) -> None:
        self.counters[name] += value

    def observe(self, name: str, duration_ms: float) -> None:
        self.latencies[name].append(duration_ms)

    @contextmanager
    def timer(self, name: str) -> Iterator[None]:
        started = time.perf_counter()
        try:
            yield
        finally:
            self.observe(name, (time.perf_counter() - started) * 1000)

    def snapshot(self) -> dict[str, object]:
        averages = {
            f"avg_{name}": round(sum(values) / len(values), 2)
            for name, values in self.latencies.items()
            if values
        }
        return {**dict(self.counters), **averages}
