"""Scorecard admission cannot launder synthetic model data into accuracy."""
import hashlib
import json
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from evaluation.proof_of_training_scorecard import assemble


def pin(path):
 return {"path":path.name,"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}

def frozen(tmp_path,kind,payload):
 src=tmp_path/"receipt.json"
 src.write_text(json.dumps(payload),encoding="utf-8")
 manifest=tmp_path/"scorecard-frozen.json"
 manifest.write_text(json.dumps({"schema":"KW_SCORECARD_INPUTS_V1",
     "status":"frozen","receipts":{kind:pin(src)}}))
 return manifest

def offline():
 return {"schema":"KW_OFFLINE_TRANSPORT_DRILL_V1",
         "status":"measured_loopback_fixture_not_field_qualified",
         "fixture":True,"network_cut_verified":True,"queue_survived_restart":True,
         "lost_ack_idempotent_reack":True,
         "queued_before":2,"delivered":2,"remaining":0,
         "observed_request_body_bytes_final":422,
         "observed_response_body_bytes_final":81,"raw_video_uploaded":False}

def localization():
 h="a"*64
 return {"schema":"KW_EQUIPMENT_LOCALIZATION_RECEIPT_V1",
         "status":"localization_measured_pending_independent_audit",
         "qualified":False,"provenance":{
          "prediction_source":"offline_groundingdino",
          "localization_manifest_sha256":h,"presence_protocol_sha256":h,"prompts_sha256":h,
          "source_video_sha256_by_scene":{f"scene{i}":h for i in range(4)},
          "annotations_sha256_by_scene":{f"scene{i}":h for i in range(4)}},
         "metrics":{"tp":4,"fp":2,"fn":1},
         "per_class":{"training_panel":{"tp":4,"fp":2,"fn":1}}}

def test_no_sources_all_pillars_blocked():
 x=assemble(None)
 assert x["qualified"] is False
 assert len(x["pillars"])==6
 assert all(v["state"]=="not_qualified" and v["metric"] is None
            for v in x["pillars"].values())

def test_real_measured_local_http_bytes_never_become_field_claim(tmp_path):
 x=assemble(frozen(tmp_path,"offline_transport",offline()))
 assert x["pillars"]["offline_transport"]["state"]=="measured_loopback_fixture_only"
 assert x["pillars"]["offline_transport"]["metric"]["request_body_bytes"]==422
 assert x["pillars"]["attendance"]["metric"] is None
 assert x["qualified"] is False
 assert "/tmp/" not in json.dumps(x)

def test_candidate_real_model_metrics_always_pending_external_audit(tmp_path):
 x=assemble(frozen(tmp_path,"equipment_localization",localization()))
 c=x["pillars"]["equipment_localization"]
 assert c["state"]=="candidate_measured_not_independently_qualified"
 assert c["metric"]["per_class"]["training_panel"]["precision"]==4/6
 assert c["metric"]["per_class"]["training_panel"]["recall"]==4/5
 assert x["qualified"] is False

def test_synthetic_location_never_shows_fake_metrics(tmp_path):
 source=localization()
 source["status"]="synthetic_localization_test_not_qualified"
 x=assemble(frozen(tmp_path,"equipment_localization",source))
 assert x["pillars"]["equipment_localization"]["metric"] is None

@pytest.mark.parametrize("transform",[
 lambda x:x.update(qualified=True),
 lambda x:x["provenance"].update(prediction_source="synthetic_injection"),
 lambda x:x["metrics"].update(tp=99),
 lambda x:x["provenance"]["annotations_sha256_by_scene"].pop("scene1"),
])
def test_bad_source_review_metrics_block(tmp_path,transform):
 x=localization()
 transform(x)
 with pytest.raises(ValueError):
  assemble(frozen(tmp_path,"equipment_localization",x))

def test_sha_drift_or_escaped_private_path_blocks(tmp_path):
 path=frozen(tmp_path,"offline_transport",offline())
 receipt=tmp_path/"receipt.json"
 receipt.write_text(receipt.read_text()+" ")
 with pytest.raises(ValueError,match="changed"):
  assemble(path)
 path=frozen(tmp_path,"offline_transport",offline())
 doc=json.loads(path.read_text())
 doc["receipts"]["offline_transport"]["path"]="../other.json"
 path.write_text(json.dumps(doc))
 with pytest.raises(ValueError,match="external"):
  assemble(path)

def test_unsourced_attendance_fake_accuracy_is_not_presented(tmp_path):
 source={"schema":"user_named_report","qualified":True,
         "accuracy":1.0,"attendance_mae":0}
 x=assemble(frozen(tmp_path,"attendance",source))
 assert x["pillars"]["attendance"]["metric"] is None
 assert x["pillars"]["attendance"]["state"]=="not_qualified"
