"""Development-only operator notification grouping, NOT detector smoothing.

The frozen camera review cue and per-sample evidence are NEVER changed.
This class only decides when an officer might receive a *new message*
instead of another message about the same unresolved condition.

A scene cue clearing is merely a notification lifecycle event; it is NOT
camera recovery, reference enrollment, verified footage, or a tamper verdict.
UNKNOWN evidence blocks cue-clear eligibility and remains independently
visible. No API, camera, attendance or compliance subsystem imports this.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import math

EVIDENCE_STATES = frozenset(("SUFFICIENT_TILES", "UNKNOWN_LOW_TEXTURE"))
SCENE_NOTICES = frozenset((
    "SCENE_REVIEW_OPEN", "SCENE_REVIEW_REMINDER",
    "SCENE_CUE_CLEARED_REVIEW_PENDING",
))
QUALITY_NOTICES = frozenset((
    "QUALITY_UNKNOWN_REVIEW", "QUALITY_UNKNOWN_REMINDER",
    "QUALITY_CUE_CLEARED_UNVERIFIED",
))
OFFLINE_PRESETS = {
    "clear30_remind300": (30.0, 300.0),
    "clear30_remind900": (30.0, 900.0),
    "clear60_remind300": (60.0, 300.0),
    "clear60_remind900": (60.0, 900.0),
    "clear120_remind900": (120.0, 900.0),
    "clear120_remind1800": (120.0, 1800.0),
}


@dataclass
class ReviewNotificationShadow:
    """Bounded-cadence advisory state; no officer acknowledgement is forged.

    Continuous *positive* scene review opens one notification and periodic
    reminders. Only sustained sufficient-texture absence of the cue can mark
    the notification cycle as cue-cleared (not proof of camera recovery).
    A reference never changes through this class.
    """

    clear_seconds: float = 60.0
    reminder_seconds: float = 900.0
    quality_start_seconds: float = 30.0
    quality_clear_seconds: float = 60.0
    elapsed: float = 0.0
    scene_active: bool = False
    clean_scene_seconds: float = 0.0
    last_scene_notice_at: float | None = None
    unknown_seconds: float = 0.0
    quality_active: bool = False
    quality_clear_duration: float = 0.0
    last_quality_notice_at: float | None = None
    notifications: Counter = field(default_factory=Counter)
    samples: int = 0
    raw_review_samples: int = 0
    raw_unknown_samples: int = 0
    scene_cue_cleared_pending_human: int = 0

    def __post_init__(self):
        for name in ("clear_seconds", "reminder_seconds",
                     "quality_start_seconds", "quality_clear_seconds"):
            value = getattr(self, name)
            if (not isinstance(value, (float, int)) or isinstance(value, bool)
                    or not math.isfinite(value) or value <= 0):
                raise ValueError(f"{name} must be finite and positive")

    def observe(self, *, review_cue: bool, evidence_status: str,
                sample_seconds: float) -> tuple[str, ...]:
        if type(review_cue) is not bool:
            raise ValueError("An explicit Boolean raw scene review cue is required")
        if evidence_status not in EVIDENCE_STATES:
            raise ValueError("Evidence status must be sufficient or unknown")
        if (not isinstance(sample_seconds, (int, float))
                or isinstance(sample_seconds, bool)
                or not math.isfinite(sample_seconds) or sample_seconds <= 0):
            raise ValueError("Sampling interval must be finite and positive")
        if review_cue and evidence_status != "SUFFICIENT_TILES":
            # The frozen fusion may review via quality-limited global cue;
            # such cases are possible while the spatial evidence is UNKNOWN.
            # They still open officer review but cannot establish recovery.
            pass

        now = self.elapsed + sample_seconds
        messages: list[str] = []
        if review_cue:
            self.raw_review_samples += 1
            self.clean_scene_seconds = 0.0
            if not self.scene_active:
                self.scene_active = True
                self.last_scene_notice_at = now
                messages.append("SCENE_REVIEW_OPEN")
            elif (self.last_scene_notice_at is not None and
                  now - self.last_scene_notice_at >= self.reminder_seconds):
                self.last_scene_notice_at = now
                messages.append("SCENE_REVIEW_REMINDER")
        elif self.scene_active:
            if evidence_status == "SUFFICIENT_TILES":
                self.clean_scene_seconds += sample_seconds
                if self.clean_scene_seconds >= self.clear_seconds:
                    self.scene_active = False
                    self.clean_scene_seconds = 0.0
                    self.last_scene_notice_at = None
                    self.scene_cue_cleared_pending_human += 1
                    messages.append("SCENE_CUE_CLEARED_REVIEW_PENDING")
            else:
                # Unknown is never evidence that camera scene has recovered.
                self.clean_scene_seconds = 0.0

        if evidence_status == "UNKNOWN_LOW_TEXTURE":
            self.raw_unknown_samples += 1
            self.unknown_seconds += sample_seconds
            self.quality_clear_duration = 0.0
            if not self.quality_active and self.unknown_seconds >= self.quality_start_seconds:
                self.quality_active = True
                self.last_quality_notice_at = now
                messages.append("QUALITY_UNKNOWN_REVIEW")
            elif (self.quality_active and self.last_quality_notice_at is not None
                  and now - self.last_quality_notice_at >= self.reminder_seconds):
                self.last_quality_notice_at = now
                messages.append("QUALITY_UNKNOWN_REMINDER")
        else:
            self.unknown_seconds = 0.0
            if self.quality_active:
                self.quality_clear_duration += sample_seconds
                if self.quality_clear_duration >= self.quality_clear_seconds:
                    self.quality_active = False
                    self.quality_clear_duration = 0.0
                    self.last_quality_notice_at = None
                    messages.append("QUALITY_CUE_CLEARED_UNVERIFIED")

        self.elapsed = now
        self.samples += 1
        self.notifications.update(messages)
        return tuple(messages)

    def summary(self) -> dict:
        return {
            "status": "OFFLINE_NOTIFICATION_CANDIDATE_NOT_DEPLOYED",
            "scene_review_active_at_end": self.scene_active,
            "quality_review_active_at_end": self.quality_active,
            "scene_cue_cleared_needs_human_review": self.scene_cue_cleared_pending_human,
            "raw_review_samples_unchanged": self.raw_review_samples,
            "raw_unknown_samples_unchanged": self.raw_unknown_samples,
            "samples": self.samples,
            "notification_counts": dict(self.notifications),
            "automatic_reference_reset": False,
            "automatic_camera_recovery": False,
            "attendance_or_compliance_actions": False,
            "interpretation": "OFFICER_NOTIFICATION_CADENCE_ONLY_NOT_EVIDENCE_FILTERING",
        }
