"""Idempotent local research-workstation start: no chat uploads or user steps.

Only the derived concordance/readiness reports are refreshed. Existing
raw/source research reports and video records remain immutable.
"""
from __future__ import annotations
import argparse
import json
import hashlib
from pathlib import Path

from .analysis import load_json
from .concordance import diagnose
from .product_readiness import generate, save_atomic, sha_json


def reconcile(*, phase3r: Path, phase3s: Path, video_report: Path,
              concordance_report: Path, clip_report: Path,
              approved_drive_manifest: Path, clip_annotations: Path,
              acceptance_report: Path, former_video_report: Path | None = None,
              external_scene_report: Path | None = None) -> dict:
    r = load_json(phase3r)
    s = load_json(phase3s)
    video = load_json(video_report)
    clips = load_json(clip_report)
    prior = load_json(former_video_report) if former_video_report and former_video_report.is_file() else None
    verified = diagnose(video, r, s, prior)
    # Recompute canonical derived concordance; stale files must NEVER be
    # re-used with new video evidence. Save only the derived JSON, atomically.
    if concordance_report.is_file():
        current = load_json(concordance_report)
        if current != verified:
            save_atomic(verified, concordance_report)
    else:
        save_atomic(verified, concordance_report)
    extra = load_json(external_scene_report) if external_scene_report is not None and external_scene_report.is_file() else None
    status = generate(r,s,video,verified,clips,approved_drive_manifest,clip_annotations,extra)
    save_atomic(status, acceptance_report)
    return status


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase3r',required=True,type=Path)
    p.add_argument('--phase3s',required=True,type=Path)
    p.add_argument('--video-report',required=True,type=Path)
    p.add_argument('--former-video-report',type=Path)
    p.add_argument('--concordance',required=True,type=Path)
    p.add_argument('--clip-report',required=True,type=Path)
    p.add_argument('--drive-manifest',required=True,type=Path)
    p.add_argument('--clip-manifest',required=True,type=Path)
    p.add_argument('--acceptance-report',required=True,type=Path)
    p.add_argument('--external-scene-report',type=Path)
    a=p.parse_args()
    result = reconcile(phase3r=a.phase3r,phase3s=a.phase3s,
                       video_report=a.video_report,
                       former_video_report=a.former_video_report,
                       concordance_report=a.concordance,clip_report=a.clip_report,
                       approved_drive_manifest=a.drive_manifest,
                       clip_annotations=a.clip_manifest,
                       acceptance_report=a.acceptance_report,external_scene_report=a.external_scene_report)
    print(json.dumps({'software_readiness':result['software_readiness'],
                      'production_release':result['production_release'],
                      'source_evidence_sha256':result['source_continuity']['video_feature_report_sha256']},indent=2))

if __name__=='__main__':main()
