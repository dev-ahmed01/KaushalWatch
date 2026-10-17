"""Phase 3P: strictly causal and NON-OPERATIONAL temporal image-quality axes.

Consumes only frozen-reference Phase3N numeric features. No raw imagery,
annotations, incident labels, scene alert mutations, privileged reference
changes, operational recovery, or production routing.

Past-sample history is TEMPORARY RESEARCH CONTEXT, not an approved reference.
It cannot certify healthy footage, and is never enrolled as a new camera
reference. Ratios are descriptive; cutoffs are exploratory only.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
import math
import re

QUALITY_HYPOTHESES = frozenset((
    "SHARPNESS_LOSS_COMPATIBLE", "REFERENCE_TEXTURE_INSUFFICIENT",
    "ILLUMINATION_CONFOUNDED", "NO_SHARPNESS_LOSS_SIGNAL",
))
SPATIAL_EVIDENCE = frozenset((
    "SUFFICIENT_TILES", "UNKNOWN_LOW_TEXTURE", "NOT_MEASURED",
))
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
METRICS = ("relative_sharpness", "relative_edge_fraction", "relative_contrast")


def _real(value: object, *, positive: bool = False) -> bool:
    return (type(value) in (int, float) and math.isfinite(value)
            and (value > 0 if positive else value >= 0))


@dataclass(frozen=True)
class _NumericObservation:
    time_s: float
    sharpness: float
    edges: float
    contrast: float
    hypothesis: str
    spatial: str
    raw_scene_review: bool | None


@dataclass
class CausalTemporalQualityShadow:
    """A bounded, immutable-source, past-only *numeric* research observer.

    All state is ephemeral. It accepts immutable physical-reference pixel SHA
    solely as an equality pin, NOT as proof of approved camera provenance.
    No annotations enter observe(); no automatic history is trusted healthy.
    """

    reference_pixel_sha256: str
    lookback_seconds: float = 30.0
    tolerance_seconds: float = 2.0
    max_gap_seconds: float = 5.0
    max_samples: int = 4096
    _history: deque[_NumericObservation] = field(default_factory=deque, init=False, repr=False)
    _last_time: float | None = field(default=None, init=False, repr=False)
    _counters: Counter = field(default_factory=Counter, init=False, repr=False)

    def __post_init__(self) -> None:
        if (type(self.reference_pixel_sha256) is not str or
                SHA256.fullmatch(self.reference_pixel_sha256) is None):
            raise ValueError("Exact lowercase 64-character frozen pixel SHA-256 pin required")
        if not _real(self.lookback_seconds, positive=True):
            raise ValueError("Positive finite lookback required")
        if not _real(self.tolerance_seconds) or self.tolerance_seconds >= self.lookback_seconds:
            raise ValueError("Finite nonnegative tolerance smaller than lookback required")
        if not _real(self.max_gap_seconds, positive=True):
            raise ValueError("Positive finite max sample gap required")
        if type(self.max_samples) is not int or self.max_samples < 2:
            raise ValueError("At least two bounded history slots required")

    def _validate(
        self, *, time_s: float, reference_pixel_sha256: str,
        features: dict, spatial_evidence_status: str, raw_scene_review: bool | None,
    ) -> _NumericObservation:
        if reference_pixel_sha256 != self.reference_pixel_sha256:
            raise ValueError("Frozen physical-reference pixel identity changed: refuse observation")
        if not _real(time_s):
            raise ValueError("Timestamp must be a finite nonnegative number")
        if self._last_time is not None and time_s <= self._last_time:
            raise ValueError("Strictly increasing sample timestamps required")
        if not isinstance(features, dict) or features.get("status") != "OFFLINE_UNCALIBRATED_VISIBILITY_AXES":
            raise ValueError("Require numeric output from frozen Phase3N visibility probe")
        if features.get("quality_hypothesis") not in QUALITY_HYPOTHESES:
            raise ValueError("Invalid visibility hypothesis")
        for field_name in ("production_integration", "automatic_recovery",
                           "blur_or_defocus_proven", "image_usable_verified",
                           "detector_review_suppressed"):
            if features.get(field_name) is not False:
                raise ValueError("Unqualified Phase3N research feature flags required: " + field_name)
        if spatial_evidence_status not in SPATIAL_EVIDENCE or raw_scene_review is not None and type(raw_scene_review) is not bool:
            raise ValueError("Explicit spatial evidence status and raw scene cue required")
        for field_name in METRICS:
            if not _real(features.get(field_name)):
                raise ValueError("Nonnegative finite quality measurement required: " + field_name)
        return _NumericObservation(
            time_s=float(time_s),
            sharpness=float(features["relative_sharpness"]),
            edges=float(features["relative_edge_fraction"]),
            contrast=float(features["relative_contrast"]),
            hypothesis=features["quality_hypothesis"],
            spatial=spatial_evidence_status,
            raw_scene_review=raw_scene_review,
        )

    def observe(
        self, *, time_s: float, reference_pixel_sha256: str, features: dict,
        spatial_evidence_status: str, raw_scene_review: bool | None,
    ) -> dict:
        """Causal: chooses only an existing past observation before appending current.

        Does not use event labels or post-onset information; no alert decisions.
        A 30-second old, annotation-free anchor is *not* assumed healthy.
        """
        current = self._validate(
            time_s=time_s, reference_pixel_sha256=reference_pixel_sha256,
            features=features, spatial_evidence_status=spatial_evidence_status,
            raw_scene_review=raw_scene_review,
        )
        had_gap = (self._last_time is not None and
                   current.time_s - self._last_time > self.max_gap_seconds)
        if had_gap:
            self._history.clear()  # Ephemeral numeric cache only. Never trusted camera reference.
            self._counters["discontinuous_history_gaps"] += 1
        minimum_time = current.time_s - self.lookback_seconds - self.tolerance_seconds
        while self._history and self._history[0].time_s < minimum_time:
            self._history.popleft()
            self._counters["aged_out_samples"] += 1
        target_time = current.time_s - self.lookback_seconds
        candidates = [
            item for item in self._history
            if abs(item.time_s - target_time) <= self.tolerance_seconds
        ]
        past = min(candidates, key=lambda item: abs(item.time_s - target_time)) if candidates else None

        status = "PAIRED_UNVERIFIED_NUMERIC_OBSERVATION"
        ratios: dict[str, float] | None = None
        confounds: list[str] = []
        if had_gap:
            status = "DISCONTINUOUS_HISTORY"
        elif past is None:
            status = "INSUFFICIENT_PAST_SAMPLE_COVERAGE"
        elif (past.spatial == "UNKNOWN_LOW_TEXTURE" or
              current.spatial == "UNKNOWN_LOW_TEXTURE"):
            status = "UNKNOWN_LOW_TEXTURE_ABSTAIN"
        elif (past.hypothesis == "REFERENCE_TEXTURE_INSUFFICIENT" or
              current.hypothesis == "REFERENCE_TEXTURE_INSUFFICIENT"):
            status = "REFERENCE_TEXTURE_INSUFFICIENT_ABSTAIN"
        elif (past.sharpness <= 1e-6 or past.edges <= 1e-6 or past.contrast <= 1e-6):
            status = "NONINFORMATIVE_PAST_DENOMINATOR_ABSTAIN"
        else:
            ratios = {
                "sharpness": round(current.sharpness / past.sharpness, 6),
                "edge_fraction": round(current.edges / past.edges, 6),
                "contrast": round(current.contrast / past.contrast, 6),
            }
            if "ILLUMINATION_CONFOUNDED" in (past.hypothesis, current.hypothesis):
                confounds.append("ILLUMINATION_UNRESOLVED")
            if "NOT_MEASURED" in (past.spatial, current.spatial):
                confounds.append("SPATIAL_EVIDENCE_NOT_MEASURED")
            if past.raw_scene_review is None or current.raw_scene_review is None:
                confounds.append("RAW_SCENE_CUE_NOT_MEASURED")
            if past.raw_scene_review or current.raw_scene_review:
                confounds.append("SCENE_REVIEW_ACTIVE_IN_PAIR")

        self._counters[status] += 1
        for confound in confounds:
            self._counters["confound:" + confound] += 1

        # Append only after comparing: the observation can NEVER be its own
        # 30s anchor. Memory remains bounded in both wall time and count.
        self._history.append(current)
        while len(self._history) > self.max_samples:
            self._history.popleft()
            self._counters["capacity_evictions"] += 1
        self._last_time = current.time_s

        return {
            "status": "OFFLINE_CAUSAL_TEMPORAL_DIAGNOSTICS_ONLY",
            "comparison_state": status,
            "time_s": current.time_s,
            "actual_past_anchor_time_s": past.time_s if past and not had_gap else None,
            "past_anchor_age_s": round(current.time_s - past.time_s, 6) if past and not had_gap else None,
            "paired_numeric_ratios": ratios,
            "confounds": confounds,
            "exploratory_sharpness_ratio_at_most_half": (
                ratios["sharpness"] <= 0.5 if ratios is not None else None
            ),
            "raw_scene_review_seen": raw_scene_review,
            "spatial_evidence_status": spatial_evidence_status,
            "ephemeral_anchor_health_verified": False,
            "trusted_reference_approved_by_this_module": False,
            "quality_or_defocus_proven": False,
            "image_usable_verified": False,
            "incident_closed_or_recovered": False,
            "automatic_reference_reset": False,
            "scene_warning_suppressed": False,
            "production_integration": False,
        }

    def summary(self) -> dict:
        return {
            "status": "OFFLINE_CAUSAL_TEMPORAL_DIAGNOSTICS_ONLY",
            "counters": dict(self._counters),
            "retained_numeric_observations": len(self._history),
            "lookback_seconds": self.lookback_seconds,
            "tolerance_seconds": self.tolerance_seconds,
            "max_gap_seconds": self.max_gap_seconds,
            "max_samples": self.max_samples,
            "source_reference_sha256_pinned_only_not_authenticated": True,
            "production_qualified": False,
            "reference_reenrollment": False,
            "operator_incident_recovery": False,
            "limitations": [
                "Past sample coverage and declared reference identity are not source authentication",
                "Ephemeral anchor is not human-approved or independently healthy",
                "Illumination and scene reviews are flagged as confounds, never suppressed",
                "Raw review state may be NOT_MEASURED; unknown must never be treated as false",
            "Raw review state is observed but never replaced, cleared, or downgraded",
                "Feature sampling requires continuous causal replay before latency and false-warning evaluation",
                "Exploratory 0.5 numeric ratio is not trained, calibrated or a deployment decision",
            ],
        }
