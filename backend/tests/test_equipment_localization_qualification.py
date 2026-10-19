"""Phase 3C adversarial localization tests: generated source only, never real accuracy."""
import copy
import csv
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]
from evaluation import equipment_localization_qualification as boxes
from evaluation import live_equipment_qualification as counts


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pin(path, root):
    return {"path": path.relative_to(root).as_posix(), "sha256": sha(path)}


def movie(path, n):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (100, 80))
    assert writer.isOpened()
    for t in range(30):
        writer.write(np.full((80, 100, 3), (n+t)%220, dtype=np.uint8))
    writer.release()
    assert cv2.VideoCapture(str(path)).isOpened()
    return path


ROI = [0.05, 0.05, 0.95, 0.95]
GT = [0.10, 0.15, 0.30, 0.35]
BOX_PIXELS = [10, 12, 30, 28]


@pytest.fixture
def protocol(tmp_path):
    model = tmp_path / "model"
    model.mkdir()
    weights = model / "model.safetensors"
    weights.write_bytes(b"ephemeral synthetic checkpoint; not real weights")
    config = model / "config.json"
    config.write_text('{"model_type":"test-only"}')
    model_pins = {p.name: sha(p) for p in (weights, config)}
    base_path = tmp_path / "count.json"
    frozen = {"source_origin":"generated CI test recording, not centre data",
              "license_basis":"locally rendered self-created test frames",
              "privacy_basis":"flat pixel fields, no humans or identity"}
    calibration = [{
        "scene_id":"CAL-SCENE-01", "recording_id":"CAL-RECORD-01",
        "site_id":"CAL-SITE-01", "camera_id":"CAL-CAMERA-01",
        "video": pin(movie(tmp_path/"cal.avi", 10), tmp_path), **frozen,
    }]
    held = []
    admission = {}
    for i in range(4):
        sid = f"HELD-SCENE-{i}"
        vid = movie(tmp_path / f"held-{i}.avi", 30+i)
        label_path = tmp_path / f"counts-{i}.csv"
        with label_path.open("w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["second", "item_id", "true_count"])
            writer.writerows([[0,"chair",1],[0,"drill",0],
                              [1,"chair",0],[1,"drill",1]])
        held.append({
            "scene_id":sid, "recording_id":f"REC-HELD-{i}",
            "site_id":"SITE-A" if i<2 else "SITE-B",
            "camera_id":"CAM-A" if i<2 else "CAM-B",
            "video":pin(vid,tmp_path), "labels":pin(label_path,tmp_path),
            "reviewer_id":"BLIND-COUNT-REVIEWER",
            "blinded_review":True,"previously_inspected":False,**frozen,
        })
        annotations = tmp_path / f"boxes-{i}.json"
        annotations.write_text(json.dumps({
            "schema":"KW_EQUIPMENT_BOX_LABELS_V1",
            "frames":[
                {"second":0,"labels":[
                    {"item_id":"chair","state":"reviewed","boxes":[GT]},
                    {"item_id":"drill","state":"reviewed","boxes":[]}]},
                {"second":1,"labels":[
                    {"item_id":"chair","state":"reviewed","boxes":[]},
                    {"item_id":"drill","state":"reviewed","boxes":[GT]}]},
            ],
        }))
        admission[sid] = {
            "labels":pin(annotations,tmp_path),"roi":ROI[:],
            "roi_basis":"fixed camera framing reviewed for CI test",
            "reviewer_id":"BOX-BLIND-REVIEWER",
            "blinded_review":True,"previously_inspected":False,
            "annotation_origin":"original CI synthetic box annotation",
            "license_basis":"generated CI annotations owned by test",
            "privacy_basis":"CI pixel geometry no natural footage",
        }
    base_path.write_text(json.dumps({
        "schema_version":1,"protocol_id":"CI-LOCALIZATION-COUNT-001",
        "status":"frozen","fixture_only":True,"policy":counts.POLICY,
        "model":{"directory":"model","files":model_pins,
                 "prompts":{"chair":"training chair","drill":"power drill"},
                 "threshold":0.35,"nms_iou":0.5,"device":"cpu"},
        "calibration":calibration,"heldout":held,
    }))
    path = tmp_path/"localization.json"
    path.write_text(json.dumps({
        "schema":"KW_EQUIPMENT_LOCALIZATION_V1","status":"frozen",
        "fixture_only":True,"policy":boxes.POLICY,
        "presence_manifest":pin(base_path,tmp_path),
        "annotations":admission,
    }))
    return path


def fake(scene, settings):
    assert set(scene) == {"scene_id","video","sha","timestamps","width","height"}
    assert set(settings) == {"prompts"}
    return {
        0.0:[
            {"label":"chair","count":1,"boxes":[BOX_PIXELS],
             "proposal_status":"unreviewed_model_proposal"},
            {"label":"drill","count":0,"boxes":[],
             "proposal_status":"unreviewed_model_proposal"}],
        1.0:[
            {"label":"chair","count":0,"boxes":[],
             "proposal_status":"unreviewed_model_proposal"},
            {"label":"drill","count":1,"boxes":[BOX_PIXELS],
             "proposal_status":"unreviewed_model_proposal"}],
    }


def update(path, action):
    doc = json.loads(path.read_text())
    action(doc)
    path.write_text(json.dumps(doc))


def update_annotation(path, scene, action):
    doc = json.loads(path.read_text())
    meta = doc["annotations"][scene]
    target = path.parent / meta["labels"]["path"]
    value = json.loads(target.read_text())
    action(value)
    target.write_text(json.dumps(value))
    meta["labels"]["sha256"] = sha(target)
    path.write_text(json.dumps(doc))


def update_base(path, action):
    doc = json.loads(path.read_text())
    base = path.parent/doc["presence_manifest"]["path"]
    payload = json.loads(base.read_text())
    action(payload)
    base.write_text(json.dumps(payload))
    doc["presence_manifest"]["sha256"] = sha(base)
    path.write_text(json.dumps(doc))


def test_clean_scored_boxes_remain_not_qualified(protocol):
    score = boxes.evaluate(protocol, injected=fake, test_fixture=True)
    assert score["qualified"] is False
    assert score["status"] == "synthetic_localization_test_not_qualified"
    assert score["metrics"]["tp"] == 8
    assert score["metrics"]["fp"] == score["metrics"]["fn"] == 0
    assert score["metrics"]["precision"] == score["metrics"]["recall"] == 1
    assert score["support"]["reviewed_negative_class_windows"] == 8
    assert len(score["provenance"]["source_video_sha256_by_scene"]) == 4
    assert score["provenance"]["prediction_source"] == "synthetic_injection"


def test_wrong_class_produces_fp_and_fn(protocol):
    def wrong(scene, settings):
        rows = fake(scene, settings)
        rows[0.0][0]["boxes"] = []
        rows[0.0][0]["count"] = 0
        rows[0.0][1]["boxes"] = [BOX_PIXELS]
        rows[0.0][1]["count"] = 1
        return rows
    r = boxes.evaluate(protocol, injected=wrong, test_fixture=True)
    assert r["metrics"]["tp"] == 4
    assert r["metrics"]["fn"] == 4
    assert r["metrics"]["fp"] == 4


def test_duplicate_box_is_penalized_without_double_matching(protocol):
    def duplicate(scene, settings):
        rows = fake(scene,settings)
        rows[0.0][0]["boxes"].append([11,13,31,29])
        rows[0.0][0]["count"] = 2
        return rows
    r = boxes.evaluate(protocol, injected=duplicate, test_fixture=True)
    assert r["metrics"]["tp"] == 8 and r["metrics"]["fp"] == 4
    assert boxes.match_boxes([GT], [GT, GT]) == (1,1,0)
    assert boxes.match_boxes([GT], [[0.7,0.7,0.8,0.8]]) == (0,1,1)
    assert boxes.match_boxes([], []) == (0,0,0)


def test_overlap_assignment_is_max_cardinality():
    gt = [[0.1,0.1,0.4,0.4], [0.3,0.1,0.6,0.4]]
    guesses = [[0.1,0.1,0.4,0.4], [0.3,0.1,0.6,0.4]]
    assert boxes.match_boxes(gt, guesses) == (2,0,0)


def test_occluded_window_abstains_not_false_negative(protocol):
    update_annotation(protocol, "HELD-SCENE-0",
        lambda x: x["frames"][0]["labels"][0].update({"state":"unlabelable","boxes":[]}))
    score = boxes.evaluate(protocol, injected=fake, test_fixture=True)
    assert score["support"]["abstained_class_windows"] == 1
    assert score["metrics"]["tp"] == 7
    assert score["metrics"]["fn"] == 0


@pytest.mark.parametrize("change,error",[
    (lambda r:r["frames"][0].update(second=0.4), "timestamp"),
    (lambda r:r["frames"][0]["labels"].pop(), "class matrix"),
    (lambda r:r["frames"][0]["labels"].append(copy.deepcopy(r["frames"][0]["labels"][0])), "class matrix"),
])
def test_wrong_timestamp_or_incomplete_labels_fails_closed(protocol, change, error):
    update_annotation(protocol,"HELD-SCENE-0",change)
    with pytest.raises(ValueError,match=error):
        boxes.load(protocol,test_fixture=True)


def test_missing_prediction_and_extra_detector_class_fails(protocol):
    def missing(scene, settings):
        pred = fake(scene,settings)
        pred[0].pop()
        return pred
    with pytest.raises(ValueError,match="Missing class"):
        boxes.evaluate(protocol,injected=missing,test_fixture=True)
    def missing_frame(scene,settings):
        pred=fake(scene,settings)
        del pred[1.0]
        return pred
    with pytest.raises(ValueError,match="Missing frame"):
        boxes.evaluate(protocol,injected=missing_frame,test_fixture=True)


def test_invalid_roi_and_mixed_camera_roi_block(protocol):
    update(protocol,lambda x:x["annotations"]["HELD-SCENE-0"].update(roi=[0,0,1.2,1]))
    with pytest.raises(ValueError,match="ROI"):
        boxes.load(protocol,test_fixture=True)
    update(protocol,lambda x:x["annotations"]["HELD-SCENE-0"].update(roi=ROI))
    update(protocol,lambda x:x["annotations"]["HELD-SCENE-1"].update(roi=[0.1,0.1,0.9,0.9]))
    with pytest.raises(ValueError,match="conflicting"):
        boxes.load(protocol,test_fixture=True)


def test_video_and_model_hash_changes_fail_closed(protocol):
    v=protocol.parent/"held-0.avi"
    v.write_bytes(v.read_bytes()+b"source-change")
    with pytest.raises(ValueError,match="SHA-256"):
        boxes.load(protocol,test_fixture=True)
    # independent new fixture to test weight change
    # Do not use affected mutable protocol after source tampering.


def test_calibration_heldout_leakage_blocked(protocol):
    update_base(protocol,lambda b:b["heldout"][0].update(
        recording_id=b["calibration"][0]["recording_id"]))
    with pytest.raises(ValueError,match="leakage"):
        boxes.load(protocol,test_fixture=True)


def test_fixture_never_real_and_bad_injection_denied(protocol):
    with pytest.raises(ValueError,match="Synthetic"):
        boxes.load(protocol)
    with pytest.raises(ValueError,match="Synthetic injection"):
        boxes.evaluate(protocol,injected=fake)
    with pytest.raises(ValueError,match="Synthetic injection"):
        boxes.evaluate(protocol,test_fixture=True)


def test_model_snapshot_and_review_provenance_required(protocol):
    (protocol.parent/"model"/"config.json").write_text("{}")
    with pytest.raises(ValueError,match="SHA-256"):
        boxes.load(protocol,test_fixture=True)


def test_annotation_hash_and_blind_review_required(protocol):
    path=protocol.parent/"boxes-0.json"
    path.write_text(path.read_text()+" ")
    with pytest.raises(ValueError,match="SHA-256"):
        boxes.load(protocol,test_fixture=True)


def test_exhaustive_positive_negative_support_required(protocol):
    update_annotation(protocol,"HELD-SCENE-0",
        lambda r:r["frames"][0]["labels"][0].update(state="unlabelable",boxes=[]))
    update_annotation(protocol,"HELD-SCENE-1",
        lambda r:r["frames"][0]["labels"][0].update(state="unlabelable",boxes=[]))
    update_annotation(protocol,"HELD-SCENE-2",
        lambda r:r["frames"][0]["labels"][0].update(state="unlabelable",boxes=[]))
    update_annotation(protocol,"HELD-SCENE-3",
        lambda r:r["frames"][0]["labels"][0].update(state="unlabelable",boxes=[]))
    # Still four positive drill objects remain: threshold exactly passes.
    assert boxes.load(protocol,test_fixture=True)
    update_annotation(protocol,"HELD-SCENE-0",
        lambda r:r["frames"][1]["labels"][1].update(state="unlabelable",boxes=[]))
    with pytest.raises(ValueError,match="Insufficient"):
        boxes.load(protocol,test_fixture=True)
