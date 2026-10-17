"""Phase 3L — streaming OFFLINE counterfactual detector candidate comparison.

All candidates are explicitly RESEARCH ONLY. They transform the *same*
frozen detector Boolean cue without changing the detector, preserving
UNKNOWN evidence, and are scored against ALL original annotated events.

A candidate is never automatically deployed. This is not a causal
proof that a hypothesized nuisance signal was harmless or that a
false-positive rate improved on independently verified footage.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import math

VALID_EVIDENCE = frozenset(("SUFFICIENT_TILES", "UNKNOWN_LOW_TEXTURE"))
ANOMALIES = ("covered", "defocused", "moved")
LABELS = {0: "normal", 1: "covered", 2: "defocused", 3: "moved"}
CANDIDATES = (
    "frozen_baseline",
    "photometric_defer",
    "localized_defer",
    "photometric_or_local_defer",
    "coherent_translation_only",
    "sustained_raw_20s",
)


@dataclass
class CandidateGate:
    name: str
    elapsed_raw_seconds: float = 0.0
    altered_raw_review_samples: int = 0
    unknown_raw_reviews_preserved: int = 0

    def __post_init__(self):
        if self.name not in CANDIDATES:
            raise ValueError("Only frozen counterfactual candidates are allowed")

    def observe(self, *, raw_review: bool, evidence_status: str,
                cause: dict, sample_seconds: float) -> bool:
        if (type(raw_review) is not bool or evidence_status not in VALID_EVIDENCE
                or not isinstance(cause, dict)
                or not isinstance(sample_seconds, (int, float))
                or isinstance(sample_seconds, bool)
                or not math.isfinite(sample_seconds) or sample_seconds <= 0):
            raise ValueError("Counterfactual requires valid cue, evidence, cause and cadence")
        hypotheses = cause.get("hypotheses")
        phase = cause.get("translation_preset_sweep")
        if (not isinstance(hypotheses, list) or
                any(not isinstance(x,str) for x in hypotheses) or
                not isinstance(phase, dict) or
                not isinstance(phase.get("conservative"), dict) or
                type(phase["conservative"].get("candidate_global_translation_supported")) is not bool):
            raise ValueError("Complete image diagnostics required for every sample")
        if raw_review:
            self.elapsed_raw_seconds += sample_seconds
        else:
            self.elapsed_raw_seconds = 0.0
        # Never reinterpret an unknown-quality global fallback alert as a
        # clean or healthy view. Uncertainty remains independently visible.
        if evidence_status == "UNKNOWN_LOW_TEXTURE":
            if raw_review:
                self.unknown_raw_reviews_preserved += 1
            return raw_review
        output = raw_review
        if self.name == "photometric_defer":
            output = raw_review and "PHOTOMETRIC_SHIFT_COMPATIBLE" not in hypotheses
        elif self.name == "localized_defer":
            output = raw_review and "LOCAL_FOREGROUND_OR_OCCLUSION_COMPATIBLE" not in hypotheses
        elif self.name == "photometric_or_local_defer":
            output = raw_review and not (
                "PHOTOMETRIC_SHIFT_COMPATIBLE" in hypotheses
                or "LOCAL_FOREGROUND_OR_OCCLUSION_COMPATIBLE" in hypotheses
            )
        elif self.name == "coherent_translation_only":
            output = raw_review and phase["conservative"]["candidate_global_translation_supported"]
        elif self.name == "sustained_raw_20s":
            output = raw_review and self.elapsed_raw_seconds >= 20.0
        if raw_review and not output:
            self.altered_raw_review_samples += 1
        if output and not raw_review:
            raise RuntimeError("Candidate invented a new camera scene warning")
        return bool(output)


@dataclass
class CandidateScore:
    """Streaming truth-bound event scoring; annotation called on EVERY frame."""
    name: str
    fps: float
    sampled: Counter = field(default_factory=Counter)
    review: Counter = field(default_factory=Counter)
    fresh_normal_episodes: int = 0
    normal_frames: int = 0
    previous_kind: int | None = None
    previous_review: bool = False
    current_event: dict | None = None
    events: list[dict] = field(default_factory=list)

    def __post_init__(self):
        if not math.isfinite(self.fps) or self.fps <= 0:
            raise ValueError("Positive source FPS required")

    def annotation(self, frame_number: int, label: int) -> None:
        if type(frame_number) is not int or frame_number < 1 or label not in LABELS:
            raise ValueError("Invalid annotation")
        if label == 0:
            self.normal_frames += 1
        if label == self.previous_kind:
            return
        if self.current_event is not None:
            self.events.append(self.current_event)
            self.current_event = None
        if label != 0:
            self.current_event = {
                "class": LABELS[label], "start_frame": frame_number,
                "preexisting_at_onset": self.previous_review,
                "fresh_review_frame": None, "had_review": False, "sampled_frames": 0,
            }
        self.previous_kind = label

    def observation(self, frame_number: int, label: int, review: bool) -> None:
        if type(review) is not bool or label != self.previous_kind:
            raise ValueError("Out-of-sequence or nonBoolean candidate observation")
        name = LABELS[label]
        self.sampled[name] += 1
        if label != 0 and self.current_event is not None:
            self.current_event["sampled_frames"] += 1
        if review:
            self.review[name] += 1
            if label == 0 and not self.previous_review:
                self.fresh_normal_episodes += 1
            if label != 0 and self.current_event is not None:
                self.current_event["had_review"] = True
                if (not self.previous_review
                        and not self.current_event["preexisting_at_onset"]
                        and self.current_event["fresh_review_frame"] is None):
                    self.current_event["fresh_review_frame"] = frame_number
        self.previous_review = review

    def result(self) -> dict:
        events = list(self.events)
        if self.current_event is not None:
            events.append(self.current_event)
        normal_hours = self.normal_frames / self.fps / 3600.0
        by_class = {}
        for name in ANOMALIES:
            selection = [event for event in events if event["class"] == name]
            fresh = [event for event in selection if event["fresh_review_frame"] is not None]
            delays = [(e["fresh_review_frame"] - e["start_frame"]) / self.fps for e in fresh]
            by_class[name] = {
                "events": len(selection),
                "unsampled_events": sum(e["sampled_frames"] == 0 for e in selection),
                "unsampled_event_start_frames": [e["start_frame"] for e in selection if e["sampled_frames"] == 0],
                "fresh_review_events": len(fresh),
                "any_review_events": sum(e["had_review"] for e in selection),
                "preexisting_review_at_onset": sum(e["preexisting_at_onset"] for e in selection),
                "max_fresh_delay_seconds": round(max(delays), 3) if delays else None,
                "fresh_event_start_frames": [e["start_frame"] for e in fresh],
                "any_review_event_start_frames": [e["start_frame"] for e in selection if e["had_review"]],
            }
        return {
            "name": self.name, "sampled_by_class": dict(self.sampled),
            "review_samples_by_class": dict(self.review),
            "normal_review_fraction": (
                round(self.review["normal"] / self.sampled["normal"], 6)
                if self.sampled["normal"] else None
            ),
            "normal_review_episodes_per_normal_hour": (
                round(self.fresh_normal_episodes / normal_hours, 6)
                if normal_hours else None
            ),
            "normal_hours": round(normal_hours, 6),
            "events": by_class,
        }


@dataclass
class OfflineCandidateComparison:
    fps: float
    gates: dict[str, CandidateGate] = field(init=False)
    scores: dict[str, CandidateScore] = field(init=False)
    unknown_samples_by_class: Counter = field(default_factory=Counter)
    total_observations: int = 0
    last_frame: int = 0
    is_full_recording: bool = False

    def __post_init__(self):
        self.gates = {name: CandidateGate(name) for name in CANDIDATES}
        self.scores = {
            name: CandidateScore(name, self.fps) for name in CANDIDATES
        }

    def annotation(self, frame: int, label: int) -> None:
        if frame != self.last_frame + 1:
            raise ValueError("Annotation frame numbers must be continuous")
        for scorer in self.scores.values():
            scorer.annotation(frame, label)
        self.last_frame = frame

    def observation(self, frame: int, label: int, *, raw_review: bool,
                    evidence_status: str, cause: dict, sample_seconds: float) -> None:
        if frame != self.last_frame:
            raise ValueError("Observation must match most recent annotation frame")
        if evidence_status not in VALID_EVIDENCE:
            raise ValueError("Bad evidence status")
        if evidence_status == "UNKNOWN_LOW_TEXTURE":
            self.unknown_samples_by_class[LABELS[label]] += 1
        for name, gate in self.gates.items():
            transformed = gate.observe(
                raw_review=raw_review, evidence_status=evidence_status,
                cause=cause, sample_seconds=sample_seconds,
            )
            self.scores[name].observation(frame, label, transformed)
        self.total_observations += 1

    def result(self, *, full: bool) -> dict:
        stats = {name: score.result() for name, score in self.scores.items()}
        baseline = stats["frozen_baseline"]
        decision = {}
        for name, candidate in stats.items():
            lost = {}
            added = {}
            lost_any = {}
            for event in ANOMALIES:
                before = set(baseline["events"][event]["fresh_event_start_frames"])
                after = set(candidate["events"][event]["fresh_event_start_frames"])
                lost[event] = sorted(before - after)
                added[event] = sorted(after - before)
                baseline_any = set(baseline["events"][event]["any_review_event_start_frames"])
                candidate_any = set(candidate["events"][event]["any_review_event_start_frames"])
                lost_any[event] = sorted(baseline_any - candidate_any)
                if baseline["events"][event]["events"] != candidate["events"][event]["events"]:
                    raise RuntimeError("Counterfactuals disagree about ground truth")
            base_fraction = baseline["normal_review_fraction"]
            new_fraction = candidate["normal_review_fraction"]
            improvement = (
                round(base_fraction - new_fraction, 6)
                if base_fraction is not None and new_fraction is not None else None
            )
            if not full:
                interpretation = "PREVIEW_ONLY_NOT_COMPARABLE"
            elif any(candidate["events"][event]["unsampled_events"] > 0 for event in ANOMALIES):
                interpretation = "BLOCKED_UNSAMPLED_ANNOTATED_EVENTS"
            elif any(lost[event] or lost_any[event] for event in ANOMALIES):
                interpretation = "BLOCKED_KNOWN_EVENT_REGRESSION"
            elif name == "frozen_baseline":
                interpretation = "FROZEN_BASELINE"
            elif improvement is None or improvement <= 0:
                interpretation = "NO_OBSERVED_RAW_NORMAL_REVIEW_REDUCTION"
            else:
                interpretation = "DEVELOPMENT_NO_EVENT_LOSS_OBSERVED_NOT_QUALIFIED"
            decision[name] = {
                **candidate,
                "raw_normal_fraction_reduction_vs_baseline": improvement,
                "lost_baseline_fresh_event_start_frames": lost,
                "lost_baseline_any_review_event_start_frames": lost_any,
                "gained_fresh_event_start_frames": added,
                "candidate_altered_raw_review_samples": self.gates[name].altered_raw_review_samples,
                "unknown_review_samples_preserved": self.gates[name].unknown_raw_reviews_preserved,
                "interpretation": interpretation,
                "authorized_for_deployment": False,
            }
        return {
            "status": (
                "FULL_RECORDING_COUNTERFACTUAL_DEVELOPMENT_NOT_HELD_OUT"
                if full else "PREVIEW_ONLY_COUNTERFACTUAL_NOT_COMPARABLE"
            ),
            "candidate_comparisons": decision,
            "unknown_samples_by_class_unchanged": dict(self.unknown_samples_by_class),
            "total_sampled_observations": self.total_observations,
            "production_qualified": False,
            "deployable_candidate_selected": None,
            "automatic_reference_recovery": False,
            "frozen_detector_modified": False,
            "limitations": [
                "Counterfactuals are Boolean postprocessing, not retrained detector algorithms",
                "Annotation-normal is not independently verified healthy/usable footage",
                "Event detection is evaluated across complete annotations, not selected windows",
                "Changes to onset/preexisting status can alter fresh-event definitions",
                "All candidate reductions are DEVELOPMENT hypothesis tests, never validated false-positive rates",
                "No changes to production CameraTrust, attendance, compliance or private reference store",
            ],
        }
