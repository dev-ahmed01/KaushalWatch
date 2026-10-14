"""Experimental tile-localized obstruction evidence for fixed CCTV cameras.

Detect a persistent edge-adjacent patch where a minority of scene tiles
change while most background tiles remain recognizable. This is a
development-set cue and cannot prove deliberate camera tampering.
"""
from __future__ import annotations

import cv2
import numpy as np


def localized_occlusion_candidate(
    reference: np.ndarray,
    current: np.ndarray,
    previous: np.ndarray | None,
) -> bool:
    """Require connected, stable, localized change without global drift.

    Normal day/night regime changes usually alter a large fraction of the
    image. Slow-moving people or a static sign may still create false alarms;
    this heuristic must not be promoted without independent testing.
    """
    if previous is None:
        return False

    def grayscale_small(frame: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        return cv2.resize(
            gray, (192, 144), interpolation=cv2.INTER_AREA
        ).astype(np.float32)

    baseline = grayscale_small(reference)
    image = grayscale_small(current)
    prev = grayscale_small(previous)

    # Correct additive exposure changes using the median across the frame.
    # An obstruction covering a minority of the field cannot dominate it.
    exposure_offset = float(np.median(image - baseline))
    reference_change = np.abs(image - baseline - exposure_offset)
    temporal_change = np.abs(image - prev)

    def tile_average(matrix: np.ndarray) -> np.ndarray:
        return matrix.reshape(6, 24, 8, 24).mean(axis=(1, 3))

    changed = tile_average(reference_change)
    temporal = tile_average(temporal_change)
    stable_changed = (changed >= 24.0) & (temporal <= 6.0)
    changed_count = int(np.count_nonzero(changed >= 24.0))
    unchanged_count = int(np.count_nonzero(changed < 12.0))
    # Reject widespread lighting, large scene differences, and very small
    # foreground objects before checking the connected regions.
    if changed_count < 6 or changed_count > 18 or unchanged_count < 26:
        return False

    groups, _, boxes, _ = cv2.connectedComponentsWithStats(
        stable_changed.astype(np.uint8), connectivity=4
    )
    for index in range(1, groups):
        x, y, width, height, count = map(int, boxes[index])
        edge_adjacent = x == 0 or y == 0 or x + width == 8 or y + height == 6
        if (
            6 <= count <= 18
            and width >= 2 and height >= 2
            and edge_adjacent
        ):
            return True
    return False
