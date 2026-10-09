"""Spatial background-change diagnostics. DEVELOPMENT SHADOW ONLY.

A local median from 10 seconds of independently confirmed healthy video is
used for this short-window *experiment*. This is NOT a verified operational
reference and MUST NOT auto-enroll or alter CameraTrust evidence decisions.

A poor-texture frame yields UNKNOWN rather than evidence of stability/motion.
Tile agreement is not reliable proof that the camera itself moved.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

THRESHOLDS = (0.45, 0.55, 0.65)
TILE_CORR_CUTOFF = 0.40
SIZE = (192, 144)
ROWS, COLS = 6, 8


def _small(image: np.ndarray) -> np.ndarray:
    if image is None or image.size == 0:
        raise ValueError("frame is required")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    return cv2.GaussianBlur(cv2.resize(gray, SIZE), (3, 3), 0.7)


def spatial_metrics(reference: np.ndarray, current: np.ndarray) -> dict:
    """Compare localized structural texture, not whole-frame brightness."""
    a = _small(reference).astype(np.float32)
    b = _small(current).astype(np.float32)
    # Normalized local correlations are invariant to additive brightness
    # shifts but not robust to a full IR/visible or heavy weather transition.
    # Treat such cases as UNKNOWN, not automatically as a shifted camera.
    def tiles(image):
        return image.reshape(ROWS, 24, COLS, 24).transpose(
            0, 2, 1, 3
        ).reshape(ROWS * COLS, 24 * 24)
    ta, tb = tiles(a), tiles(b)
    aa = ta - ta.mean(axis=1, keepdims=True)
    bb = tb - tb.mean(axis=1, keepdims=True)
    sa = np.sqrt(np.mean(aa * aa, axis=1))
    sb = np.sqrt(np.mean(bb * bb, axis=1))
    textured = (sa >= 7.0) & (sb >= 4.0)
    denom = np.linalg.norm(aa, axis=1) * np.linalg.norm(bb, axis=1)
    similarity = np.divide(
        np.sum(aa * bb, axis=1), denom,
        out=np.zeros(ROWS * COLS, dtype=np.float32),
        where=denom >= 1e-5,
    )
    similarity = np.clip(similarity, -1.0, 1.0)
    changed = textured & (similarity < TILE_CORR_CUTOFF)
    eligible = int(textured.sum())
    changed_count = int(changed.sum())
    quadrant_counts = (
        int(changed.reshape(ROWS, COLS)[0:3, 0:4].sum()),
        int(changed.reshape(ROWS, COLS)[0:3, 4:8].sum()),
        int(changed.reshape(ROWS, COLS)[3:6, 0:4].sum()),
        int(changed.reshape(ROWS, COLS)[3:6, 4:8].sum()),
    )
    quadrants = sum(n >= 2 for n in quadrant_counts)
    qualified = eligible >= 12 and eligible / (ROWS * COLS) >= 0.30
    return {
        "evidence_status": "SUFFICIENT_TILES" if qualified else "UNKNOWN_LOW_TEXTURE",
        "eligible_tiles": eligible,
        "changed_tiles": changed_count,
        "changed_fraction": round(changed_count / eligible, 5) if eligible else None,
        "changed_quadrants": quadrants,
        "changed_by_quadrant": list(quadrant_counts),
        "median_tile_correlation": round(
            float(np.median(similarity[textured])), 5
        ) if eligible else None,
        "median_baseline_tile_texture": round(float(np.median(sa)), 3),
        "median_current_tile_texture": round(float(np.median(sb)), 3),
    }


@dataclass
class SpatialSceneShadow:
    warmup_seconds: float = 10.0
    confirm_seconds: float = 12.0
    elapsed: float = 0.0
    warmup: list[np.ndarray] = field(default_factory=list, repr=False)
    temporary_reference: np.ndarray | None = field(default=None, repr=False)
    sustained: dict[str, float] = field(default_factory=dict)

    def observe(self, frame: np.ndarray, sample_seconds: float) -> dict:
        if not np.isfinite(sample_seconds) or sample_seconds <= 0:
            raise ValueError("sample_seconds must be finite and positive")
        self.elapsed += sample_seconds
        if self.temporary_reference is None:
            self.warmup.append(_small(frame))
            if self.elapsed >= self.warmup_seconds:
                self.temporary_reference = np.median(
                    np.stack(self.warmup, axis=0), axis=0
                ).astype(np.uint8)
                self.warmup.clear()
            return {
                "evidence_status": "WARMUP",
                "eligible_tiles": None, "changed_tiles": None,
                "changed_fraction": None, "changed_quadrants": None,
                "median_tile_correlation": None,
                "median_baseline_tile_texture": None,
                "median_current_tile_texture": None,
                **{f"review_{int(k * 100)}": False for k in THRESHOLDS},
            }
        metrics = spatial_metrics(self.temporary_reference, frame)
        for threshold in THRESHOLDS:
            key = str(threshold)
            candidate = (
                metrics["evidence_status"] == "SUFFICIENT_TILES"
                and metrics["changed_fraction"] >= threshold
                and metrics["changed_quadrants"] >= 3
            )
            self.sustained[key] = self.sustained.get(key, 0.) + sample_seconds if candidate else 0.
            metrics[f"review_{int(threshold * 100)}"] = (
                self.sustained[key] >= self.confirm_seconds
            )
        return metrics
