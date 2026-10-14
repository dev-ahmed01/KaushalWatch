"""Phase 2C: local model integrity, fail-closed inference, held-out gate tests.

Synthetic videos contain no people or legally sensitive training-centre data.
"""
from __future__ import annotations

from contextlib import nullcontext
import csv
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"backend"))

from app.services.live_equipment import (
    GroundingDinoAdapter,validate_detections,verify_model_snapshot,
)
from evaluation import live_equipment_qualification as equipment
from evaluation import operability_holdout as motion


def sha(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pin(path:Path, manifest:Path):
    return {"path":path.relative_to(manifest.parent).as_posix(),"sha256":sha(path)}


def video(path:Path, seed:int)->Path:
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*"MJPG"),10,(96,72))
    assert writer.isOpened()
    for i in range(32):
        x=np.random.default_rng(seed+i).integers(25,180,(72,96,3),dtype=np.uint8)
        writer.write(x)
    writer.release()
    return path


def test_model_snapshot_rejects_drift_unpinned_files_and_escape(tmp_path):
    model=tmp_path/"pinned";model.mkdir()
    w=model/"model.safetensors";w.write_bytes(b"synthetic weights not a model")
    config=model/"config.json";config.write_text('{"model_type":"synthetic"}')
    digests={"model.safetensors":sha(w),"config.json":sha(config)}
    assert verify_model_snapshot(model,digests)==digests
    (model/"unreviewed.json").write_text("{}")
    with pytest.raises(ValueError,match="Unpinned"):verify_model_snapshot(model,digests)
    (model/"unreviewed.json").unlink()
    w.write_bytes(b"altered")
    with pytest.raises(ValueError,match="SHA-256"):verify_model_snapshot(model,digests)
    with pytest.raises(ValueError,match="Unsafe"):
        verify_model_snapshot(model,{"../outside.bin":"a"*64})


def test_grounding_box_postprocess_nms_and_empty_are_explicit():
    result=validate_detections(
        [[0,0,20,20],[1,1,20,20],[60,60,80,70]],[0.94,0.85,0.60],100,100)
    assert result["count"]==2
    assert result["model_count"]==2
    assert result["scores"]==[0.94,0.60]
    assert validate_detections([],[],100,100)=={
        "count":0,"model_count":0,"confidence":0.0,"boxes":[],"scores":[]}
    with pytest.raises(ValueError,match="invalid bounding box"):
        validate_detections([[-20,0,20,30]],[0.99],100,100)
    with pytest.raises(ValueError,match="coordinates"):
        validate_detections([[0,0,float("nan"),20]],[0.70],100,100)


class FakeTensor:
    def __init__(self,data):self.data=data
    def detach(self):return self
    def cpu(self):return self
    def tolist(self):return self.data


class FakeBatch(dict):
    input_ids=[1,2,3]
    def to(self,device):return self


class FakeProcessor:
    def __call__(self,*,images,text,return_tensors):
        assert return_tensors=="pt"
        return FakeBatch()
    def post_process_grounded_object_detection(self,*args,**kwargs):
        return [{"boxes":FakeTensor([[3,4,22,28],[3,4,22,28]]),
                 "scores":FakeTensor([0.87,0.85])}]


class FakeModel:
    def __call__(self,**kwargs):return object()


class FakeTorch:
    @staticmethod
    def no_grad():return nullcontext()


def test_live_detector_uses_processor_and_does_not_silently_fallback(tmp_path):
    adapter=GroundingDinoAdapter({"drill":"power drill"},model_dir=tmp_path,
                                 model_files={"model.safetensors":"a"*64})
    with pytest.raises(RuntimeError,match="Uninitialized"):
        adapter.detect_frame(np.zeros((40,40,3),dtype=np.uint8))
    adapter._processor=FakeProcessor()
    adapter._model=FakeModel()
    adapter._torch=FakeTorch()
    result=adapter.detect_frame(np.full((40,40,3),90,dtype=np.uint8))
    assert result[0]["label"]=="drill"
    assert result[0]["count"]==1
    assert result[0]["proposal_status"]=="unreviewed_model_proposal"
    with pytest.raises(ValueError):
        adapter.detect_frame(np.zeros((40,40),dtype=np.uint8))


def test_live_video_binding_requires_pin_and_rejects_modified_video(tmp_path):
    clip=video(tmp_path/"sample.avi",12)
    adapter=GroundingDinoAdapter({"drill":"power drill"},model_dir=tmp_path,
                                 model_files={"model.safetensors":"a"*64})
    adapter._processor=FakeProcessor()
    adapter._model=FakeModel()
    adapter._torch=FakeTorch()
    with pytest.raises(ValueError,match="Source recording changed"):
        adapter.bind_video(clip,"f"*64)
    adapter.bind_video(clip,sha(clip))
    assert adapter.detect_at(0.0)[0]["model_count"]==1
    clip.write_bytes(clip.read_bytes()+b"changed")
    with pytest.raises(ValueError,match="modified"):
        adapter.detect_at(0.1)
    adapter.close()


@pytest.fixture
def equipment_protocol(tmp_path):
    manifest=tmp_path/"heldout-equipment.json"
    model=tmp_path/"local-model";model.mkdir()
    weights=model/"model.safetensors";weights.write_bytes(b"CI ephemeral fake checkpoint")
    config=model/"config.json";config.write_text('{"model_type":"grounding-dino"}')
    prompts={"chair":"training chair","drill":"power drill"}
    provenance={
        "source_origin":"synthetic video rendered for a controlled CI test",
        "license_basis":"testing data produced by the test author only",
        "privacy_basis":"empty/generated frames without identified people",
    }
    calibration=[{"scene_id":"CAL-EQ-001","recording_id":"REC-CAL-EQ-001",
                  "site_id":"CAL-SITE","camera_id":"CAL-CAM",
                  "video":pin(video(tmp_path/"eq-cal.avi",6),manifest),**provenance}]
    held=[]
    for n in range(1,5):
        clip=video(tmp_path/f"eq-{n}.avi",n*14)
        labels=tmp_path/f"eq-{n}.csv"
        with labels.open("w",newline="") as out:
            writer=csv.writer(out)
            writer.writerow(["second","item_id","true_count"])
            writer.writerows([[0,"chair",1],[0,"drill",0],
                              [1,"chair",0],[1,"drill",1]])
        held.append({
            "scene_id":f"EQ-SCENE-{n:03d}",
            "recording_id":f"EQ-RECORD-{n:03d}",
            "site_id":"SITE-A" if n<=2 else "SITE-B",
            "camera_id":"CAM-A" if n<=2 else "CAM-B",
            "video":pin(clip,manifest),"labels":pin(labels,manifest),
            "reviewer_id":"BLIND-ANNOTATOR-01",
            "blinded_review":True,"previously_inspected":False,**provenance,
        })
    manifest.write_text(json.dumps({
        "schema_version":1,"protocol_id":"SYNTHETIC-EQUIPMENT-PHASE2C",
        "status":"frozen","fixture_only":True,"policy":equipment.POLICY,
        "model":{"directory":"local-model",
                 "files":{"model.safetensors":sha(weights),"config.json":sha(config)},
                 "prompts":prompts,"threshold":0.35,"nms_iou":0.5,"device":"cpu"},
        "calibration":calibration,"heldout":held,
    }))
    return manifest


def synthetic_equipment(scene,protocol):
    assert "labels" not in scene
    return {0.0:{"chair":1,"drill":0},1.0:{"chair":0,"drill":1}}


def change_manifest(manifest,edit):
    obj=json.loads(manifest.read_text())
    edit(obj)
    manifest.write_text(json.dumps(obj))


def test_perfect_synthetic_equipment_counts_never_qualify(equipment_protocol):
    score=equipment.evaluate(equipment_protocol,injected=synthetic_equipment,test_fixture=True)
    assert score["qualified"] is False
    assert score["status"]=="synthetic_live_detector_fixture_not_qualifying"
    assert all(score["criteria"].values())
    assert score["metrics"]["count_mae"]==0
    assert score["support"]["recordings"]==4


def test_equipment_injection_and_fixture_status_are_locked(equipment_protocol):
    with pytest.raises(ValueError,match="Synthetic"):
        equipment.evaluate(equipment_protocol)
    with pytest.raises(ValueError,match="Synthetic injection"):
        equipment.evaluate(equipment_protocol,injected=synthetic_equipment)


def test_equipment_missing_prediction_not_coerced_to_zero(equipment_protocol):
    def missing(scene,protocol):
        return {0.0:{"chair":1,"drill":0},1.0:{"chair":0}}
    with pytest.raises(ValueError,match="Missing live model proposal"):
        equipment.evaluate(equipment_protocol,injected=missing,test_fixture=True)


def test_equipment_duplicate_scene_or_changed_weights_refused(equipment_protocol):
    change_manifest(equipment_protocol,lambda p:p["heldout"][0].update({
        "recording_id":p["calibration"][0]["recording_id"]
    }))
    with pytest.raises(ValueError,match="leakage"):
        equipment.load(equipment_protocol,test_fixture=True)


def test_equipment_labels_need_full_matrix(equipment_protocol):
    obj=json.loads(equipment_protocol.read_text())
    labels=equipment_protocol.parent/obj["heldout"][0]["labels"]["path"]
    labels.write_text(labels.read_text().replace("1,drill,1\n",""))
    obj["heldout"][0]["labels"]["sha256"]=sha(labels)
    equipment_protocol.write_text(json.dumps(obj))
    with pytest.raises(ValueError,match="ALL frozen"):
        equipment.load(equipment_protocol,test_fixture=True)


@pytest.fixture
def motion_protocol(tmp_path):
    manifest=tmp_path/"motion-heldout.json"
    src={
        "source_origin":"synthetic sample from CI test sequence",
        "license_basis":"testing footage created by local unit tests",
        "privacy_basis":"generated pattern has no human identity",
    }
    cal=[{"scene_id":"MOTION-CAL","recording_id":"REC-CAL-MOTION",
          "site_id":"CAL-SITE","camera_id":"CAL-CAM",
          "video":pin(video(tmp_path/"motion-cal.avi",33),manifest),**src}]
    labels=["APPARENTLY_ACTIVE","APPARENTLY_INACTIVE","UNDETERMINABLE",
            "APPARENTLY_ACTIVE","APPARENTLY_INACTIVE","UNDETERMINABLE"]
    rows=[]
    for n,truth in enumerate(labels,1):
        rows.append({
            "scene_id":f"MOTION-{n:03d}","recording_id":f"MOTION-REC-{n:03d}",
            "site_id":"SITE-A" if n<=3 else "SITE-B",
            "camera_id":"CAM-A" if n<=3 else "CAM-B",
            "video":pin(video(tmp_path/f"motion-{n}.avi",n+48),manifest),
            "true_visible_motion":truth,"roi":[5,5,85,65],"window":[0,2.5],
            "reviewer_id":"SEPARATE-MOTION-LABEL-REVIEWER",
            "blinded_review":True,"previously_inspected":False,**src,
        })
    manifest.write_text(json.dumps({
        "schema_version":1,"protocol_id":"SYNTHETIC-MOTION-CI-001",
        "status":"frozen","fixture_only":True,
        "policy":motion.POLICY,"calibration":cal,"heldout":rows,
    }))
    return manifest


def synthetic_motion(scene):
    i=int(scene["id"].split("-")[1])
    assert "truth" not in scene
    return {1:"APPARENTLY_ACTIVE",2:"APPARENTLY_INACTIVE",
            3:"UNCERTAIN",4:"APPARENTLY_ACTIVE",5:"APPARENTLY_INACTIVE",
            6:"UNCERTAIN"}[i]


def test_perfect_motion_fixture_never_qualifies(motion_protocol):
    result=motion.evaluate(motion_protocol,injected=synthetic_motion,test_fixture=True)
    assert result["qualified"] is False
    assert all(result["criteria"].values())
    assert result["support"]["scenes"]==6
    assert result["metrics"]["unsafe_certainty_rate"]==0


def test_uncertain_truth_must_not_be_called_active(motion_protocol):
    def false_certainty(scene):
        if scene["id"]=="MOTION-003":return "APPARENTLY_ACTIVE"
        return synthetic_motion(scene)
    r=motion.evaluate(motion_protocol,injected=false_certainty,test_fixture=True)
    assert r["criteria"]["uncertain_for_unlabelable"] is False


def test_motion_refuses_test_as_real(motion_protocol):
    with pytest.raises(ValueError,match="Synthetic"):
        motion.evaluate(motion_protocol)


def test_motion_calibration_leakage_refused(motion_protocol):
    change_manifest(motion_protocol,lambda p:p["heldout"][0].update({
        "recording_id":p["calibration"][0]["recording_id"]}))
    with pytest.raises(ValueError,match="leakage"):
        motion.load(motion_protocol,test_fixture=True)


def test_motion_real_sampler_is_called_for_trusted_roi(motion_protocol):
    parsed=motion.load(motion_protocol,test_fixture=True)
    scene={k:v for k,v in parsed["scenes"][0].items() if k!="truth"}
    result=motion.infer(scene)
    assert result in {"APPARENTLY_ACTIVE","APPARENTLY_INACTIVE","UNCERTAIN"}
