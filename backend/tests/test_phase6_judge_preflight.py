"""Phase 6: controlled source freeze and safe reset are adversarially tested."""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"backend"))
from scripts import judge_reset_guard as guard
from scripts import verify_judge_sources as sources
from scripts.prepare_demo_state import prepare_demo_state


def write_json(path:Path,value):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(value),encoding="utf-8")


def test_real_committed_procedural_videos_are_sha_verified():
 receipt=sources.verify(ROOT)
 assert receipt["qualified"] is False
 assert len(receipt["clips"])==3
 assert receipt["status"]=="procedural_sources_verified_not_real_field_evidence"


def test_changed_source_and_manifest_never_pass(tmp_path):
 media=tmp_path/"web"/"public"/"camera-trust"
 media.mkdir(parents=True)
 clips={}
 for stem in sources.STEMS:
  data=(stem*100).encode()
  (media/(stem+".mp4")).write_bytes(data)
  clips[stem]={"sha256":hashlib.sha256(data).hexdigest()}
 write_json(media/"manifest.json",
  {"schema":"KW_SUBMISSION_SAMPLE_MEDIA_V1",
   "provenance":sources.PROVENANCE,"clips":clips})
 receipt=sources.verify(tmp_path)
 assert receipt["qualified"] is False
 (media/"workshop-floor.mp4").write_bytes(b"tampered"*120)
 with pytest.raises(ValueError,match="changed"):
  sources.verify(tmp_path)
 (media/"workshop-floor.mp4").write_bytes(("workshop-floor"*100).encode())
 write_json(media/"manifest.json",
  {"schema":"KW_SUBMISSION_SAMPLE_MEDIA_V1","provenance":"UNVERIFIED_CCTV","clips":clips})
 with pytest.raises(ValueError,match="contract"):
  sources.verify(tmp_path)


def test_true_simulated_seed_may_be_reset_but_its_raw_recordings_are_preserved(tmp_path):
 path=tmp_path/"data"
 prepare_demo_state(path)
 (path/"raw").mkdir(exist_ok=True)
 raw=path/"raw"/"KEEP-THIS.avi"
 raw.write_bytes(b"not deleted")
 report=guard.validate(path)
 assert report["safe_to_reset_simulated_state"] is True
 assert raw.read_bytes()==b"not deleted"
 assert "cases.json" in report["existing_record_counts"]


def test_unknown_centre_case_blocks_reset(tmp_path):
 path=tmp_path/"data"
 prepare_demo_state(path)
 cases=path/"cases.json"
 records=json.loads(cases.read_text())
 records[0]["centre_id"]="REAL-CENTRE-01"
 write_json(cases,records)
 with pytest.raises(ValueError,match="Unknown centre"):
  guard.validate(path)


def test_unlabelled_real_history_blocks_reset(tmp_path):
 path=tmp_path/"data"
 prepare_demo_state(path)
 doc=path/"analysis_history.json"
 records=json.loads(doc.read_text())
 records[0]["details"].pop("simulated",None)
 write_json(doc,records)
 with pytest.raises(ValueError,match="Non-simulated"):
  guard.validate(path)


def test_unindexed_photo_blocks_reset(tmp_path):
 path=tmp_path/"data"
 prepare_demo_state(path)
 (path/"evidence"/"possible-real-camera.jpg").write_bytes(b"other footage")
 with pytest.raises(ValueError,match="Unindexed"):
  guard.validate(path)


def test_tampered_synthetic_evidence_blocks_reset(tmp_path):
 path=tmp_path/"data"
 prepare_demo_state(path)
 photo=next((path/"evidence").glob("*.jpg"))
 photo.write_bytes(photo.read_bytes()+b"changed")
 with pytest.raises(ValueError,match="Missing/tampered"):
  guard.validate(path)


def test_non_demo_settings_and_real_edge_receipt_block(tmp_path):
 path=tmp_path/"data"
 prepare_demo_state(path)
 settings=path/"centre_settings.json"
 config=json.loads(settings.read_text())
 config["ACTUAL-GOV-CENTRE"]={"automatic_analysis":True}
 write_json(settings,config)
 with pytest.raises(ValueError,match="Non-demo centre settings"):
  guard.validate(path)
 del config["ACTUAL-GOV-CENTRE"]
 write_json(settings,config)
 write_json(path/"edge_events.json",[{"event_id":"EDGE-REAL-0001",
   "payload":{"centre_id":"DEMO-KA-104","details":{"simulated":False}}}])
 with pytest.raises(ValueError,match="Real or unknown edge"):
  guard.validate(path)


def test_symlinked_evidence_directory_is_rejected(tmp_path):
 path=tmp_path/"data"
 prepare_demo_state(path)
 # An ordinary new, empty synthetic folder is not an alias for camera storage.
 target=tmp_path/"external-private"
 target.mkdir()
 aliased=tmp_path/"alias-data"
 aliased.mkdir()
 (aliased/"evidence").symlink_to(target,target_is_directory=True)
 with pytest.raises(ValueError,match="Unsafe evidence"):
  guard.validate(aliased)


def test_stale_edge_queue_and_scheduler_block_clean_judge_reseed(tmp_path):
 path=tmp_path/"data"
 prepare_demo_state(path)
 (path/"edge").mkdir(exist_ok=True)
 write_json(path/"edge"/"queue.json",[{"event_id":"EDGE-OLD-EVENT","payload":{"centre_id":"DEMO-KA-104"}}])
 with pytest.raises(ValueError,match="Pending local edge"):
  guard.validate(path)
 write_json(path/"edge"/"queue.json",[])
 write_json(path/"edge"/"schedule-state.json",{"last_run":"yesterday"})
 with pytest.raises(ValueError,match="Pending local edge"):
  guard.validate(path)
 write_json(path/"edge"/"schedule-state.json",{})
 assert guard.validate(path)["safe_to_reset_simulated_state"] is True


def test_symlinked_data_root_cannot_retarget_safe_demo_reset(tmp_path):
 data=tmp_path/"real-data"
 prepare_demo_state(data)
 alias=tmp_path/"fake-demo"
 alias.symlink_to(data,target_is_directory=True)
 with pytest.raises(ValueError,match="root cannot be symlinked"):
  guard.validate(alias)
