"""Research-camera audits must remain private and explicitly nonqualifying."""
from __future__ import annotations
import hashlib
import json
import stat
from pathlib import Path
import sys

import cv2
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts import audit_private_camera_clips as audit


def prepared(tmp_path):
    folder=tmp_path/"isolated-private-footage"
    folder.mkdir()
    files=[]
    for name in audit.SOURCES:
        source=folder/name
        source.write_bytes(b"\x00\x00\x00\x18ftyp"+b"\x00"*10_000)
        files.append({"file":name,"sha256":hashlib.sha256(source.read_bytes()).hexdigest()})
    manifest={
        "schema":"KW_PRIVATE_FOOTAGE_SELECTION_V1",
        "independent_holdout":False,
        "training_centre_recording":False,
        "public_distribution_authorized":False,
        "shortlist":files,
    }
    (folder/"private-source-manifest.json").write_text(json.dumps(manifest))
    return folder,manifest


def test_bounded_pinned_development_sources_are_allowed_for_private_audit(tmp_path):
    folder,source=prepared(tmp_path)
    pins=audit.validate_sources(folder,source,{"KAUSHALWATCH_ENV":"development"})
    assert len(pins)==6


@pytest.mark.parametrize("mode", ["pilot","production","prod","staging"])
def test_protected_environments_reject_research_media(tmp_path,mode):
    folder,source=prepared(tmp_path)
    with pytest.raises(ValueError,match="Protected runtime"):
        audit.validate_sources(folder,source,{"KAUSHALWATCH_ENV":mode})


@pytest.mark.parametrize("key,value",[
    ("independent_holdout",True),
    ("training_centre_recording",True),
    ("public_distribution_authorized",True),
    ("schema","FAKE_RELEASE"),
])
def test_bad_promotion_claims_block(tmp_path,key,value):
    folder,source=prepared(tmp_path)
    source[key]=value
    with pytest.raises(ValueError,match="improperly qualified"):
        audit.validate_sources(folder,source,{})


def test_tampering_and_symlinks_fail_closed(tmp_path):
    folder,source=prepared(tmp_path)
    clip=folder/next(iter(audit.SOURCES))
    clip.write_bytes(clip.read_bytes()+b"altered")
    with pytest.raises(ValueError,match="digest drift"):
        audit.validate_sources(folder,source,{})
    folder,source=prepared(tmp_path)
    clip=folder/next(iter(audit.SOURCES))
    clip.unlink()
    clip.symlink_to(folder/list(audit.SOURCES)[1])
    with pytest.raises(ValueError,match="Source missing"):
        audit.validate_sources(folder,source,{})


def test_score_table_uses_known_development_labels_not_accuracy(monkeypatch,tmp_path):
    folder,manifest=prepared(tmp_path)
    def fake_score(path,label,start,positive):
        return {
            "label":label,"pre_event_samples":10,
            "pre_event_untrusted":2 if label=="normal" else 0,
            "annotated_event_samples":20 if label!="normal" else 0,
            "event_untrusted":5 if label!="normal" else 0,
        }
    monkeypatch.setattr(audit,"score_clip",fake_score)
    result=audit.evaluate(folder,manifest,{})
    assert result["summary"]=={
        "clips":6,"positive_event_samples":80,
        "positive_event_samples_untrusted":20,
        "pre_event_and_normal_samples":60,
        "pre_event_and_normal_samples_untrusted":4,
    }
    assert result["independently_held_out"] is False
    assert result["institutional_training_accuracy"] is False
    assert result["model_promoted"] is False
    assert result["physical_tamper_proven"] is False
    assert result["not_full_camera_worker_or_continuous_stream"] is True
    assert result["secrets_or_source_media_exported"] is False


def test_exclusive_private_receipt_permissions(tmp_path):
    target=tmp_path/"audit.json"
    audit.write_exclusive(target,{"schema":audit.SCHEMA})
    assert stat.S_IMODE(target.stat().st_mode)==0o600
    with pytest.raises(FileExistsError):
        audit.write_exclusive(target,{})
    with pytest.raises(ValueError):
        audit.write_exclusive(ROOT/"private-clip-result.json",{})


def test_real_opencv_decodes_synthetic_reel_with_unchanged_baseline(tmp_path):
    # Tests execution semantics only: generated pixels are not source footage.
    path=tmp_path/"normal_control_1.mp4"
    v=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*"mp4v"),3.0,(96,96))
    assert v.isOpened()
    for idx in range(63):
        img=np.zeros((96,96,3),dtype=np.uint8)
        cv2.rectangle(img,(10+(idx%3),20),(75,75),(145,185,205),-1)
        v.write(img)
    v.release()
    result=audit.score_clip(path,"normal",135,None)
    assert result["pre_event_samples"]==21
    assert result["annotated_event_samples"]==0
    assert result["decoded_frames"]==63
    assert result["first_frame_reference_verified"] is False
    assert all(k in result["reason_counts"]["pre"] for k in ("blur","dark","frozen","shift"))
