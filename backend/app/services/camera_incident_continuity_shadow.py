"""Annotation-aware incident continuity research state (not operational alerts).

The word 'recovery' here always means only a raw *cue-clearing candidate*,
never verified camera health. A warning active at incident onset is not a
new incident detection. Unknown structural evidence cannot clear an alert.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import math

CLASSES = {0:"normal",1:"covered",2:"defocused",3:"moved"}
STATUS = frozenset(("SUFFICIENT_TILES","UNKNOWN_LOW_TEXTURE"))


@dataclass
class IncidentContinuityShadow:
    """Continuous sampled-score timeline without changing any raw cue."""
    clear_seconds:float=60.0
    previous_label:int|None=None
    previous_review:bool=False
    episode_open:bool=False
    clean_seconds:float=0.0
    annotated_event_open:bool=False
    last_event_name:str|None=None
    post_event_carry_seconds:float=0.0
    counters:Counter=field(default_factory=Counter)
    samples:int=0

    def __post_init__(self):
        if (not isinstance(self.clear_seconds,(float,int))
                or isinstance(self.clear_seconds,bool)
                or not math.isfinite(self.clear_seconds) or self.clear_seconds<=0):
            raise ValueError("Positive finite cue-clear duration required")

    def observe(self, *, annotation_class:int, raw_review:bool,
                spatial_evidence_status:str, sample_seconds:float)->dict:
        if (type(annotation_class) is not int or annotation_class not in CLASSES
                or type(raw_review) is not bool
                or spatial_evidence_status not in STATUS
                or not isinstance(sample_seconds,(float,int))
                or isinstance(sample_seconds,bool)
                or not math.isfinite(sample_seconds) or sample_seconds<=0):
            raise ValueError("Invalid sampled label, scene cue, evidence or elapsed interval")
        started=(annotation_class!=self.previous_label)
        preexisting_at_this_onset=bool(started and annotation_class!=0 and self.previous_review)
        if started and annotation_class!=0:
            self.counters["annotated_event_onsets"]+=1
            if self.previous_review:
                self.counters["events_warning_preexisting_at_onset"]+=1
            else:
                self.counters["events_without_warning_at_onset"]+=1
            self.annotated_event_open=True
            self.last_event_name=CLASSES[annotation_class]
            self.post_event_carry_seconds=0.0
        elif started and annotation_class==0 and self.previous_label not in (None,0):
            self.annotated_event_open=False
            self.post_event_carry_seconds=0.0
            if self.previous_review:
                self.counters["warning_carried_into_annotated_normal"]+=1
        if raw_review:
            if not self.episode_open:
                self.counters["new_raw_review_episodes"]+=1
                self.episode_open=True
            if annotation_class==0:
                self.counters["normal_review_samples"]+=1
                if self.last_event_name is not None:
                    self.post_event_carry_seconds+=sample_seconds
                    self.counters["normal_review_samples_after_event"]+=1
            if spatial_evidence_status=="UNKNOWN_LOW_TEXTURE":
                self.counters["unknown_with_review_samples"]+=1
            self.clean_seconds=0.0
        elif self.episode_open:
            if spatial_evidence_status=="SUFFICIENT_TILES":
                self.clean_seconds+=sample_seconds
                if self.clean_seconds>=self.clear_seconds:
                    self.counters["raw_cue_clear_candidates_pending_review"]+=1
                    self.episode_open=False
                    self.clean_seconds=0.0
                    self.last_event_name=None
            else:
                self.clean_seconds=0.0
                self.counters["unknown_cannot_clear_episode_samples"]+=1
        if spatial_evidence_status=="UNKNOWN_LOW_TEXTURE":
            self.counters["unknown_quality_samples"]+=1
        self.previous_label=annotation_class
        self.previous_review=raw_review
        self.samples+=1
        return {
            "status":"OFFLINE_SAMPLED_INCIDENT_CONTINUITY_NOT_DEPLOYED",
            "warning_active":self.episode_open,
            "warning_preexisting_at_new_annotation":preexisting_at_this_onset,
            "last_event_class":self.last_event_name,
            "post_event_warning_elapsed_seconds":round(self.post_event_carry_seconds,3),
            "reference_reset":False,
            "recovery_verified":False,
            "attendance_or_compliance_authorized":False,
        }

    def summary(self)->dict:
        return {
            "status":"OFFLINE_SAMPLED_INCIDENT_CONTINUITY_NOT_DEPLOYED",
            "samples":self.samples,
            "counters":dict(self.counters),
            "active_review_at_end":self.episode_open,
            "auto_reference_reset":False,
            "auto_recovery":False,
            "production_integration":False,
            "limitations":[
                "Annotator-normal is not confirmed recovered scene quality",
                "Sampled-class transitions approximate exact frame-level event onsets",
                "A cue clear candidate is not physical camera recovery",
                "No automatic incident closure, alert delivery or reference replacement",
            ],
        }
