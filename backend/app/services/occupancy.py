from __future__ import annotations
from collections import deque


class OccupancySmoother:
    def __init__(self, window: int = 5) -> None:
        self.window = deque(maxlen=window)

    def update(self, count: int) -> int:
        self.window.append(count)
        ordered = sorted(self.window)
        return int(ordered[len(ordered) // 2])


def discrepancy_pct(reported: int, observed: int) -> float:
    if reported <= 0:
        return 0.0 if observed == 0 else 100.0
    return abs(reported - observed) / reported * 100.0
