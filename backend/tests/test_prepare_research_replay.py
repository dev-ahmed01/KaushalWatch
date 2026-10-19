"""Synthetic cached clips only: never fetch Drive during CI."""
import csv
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from scripts.prepare_research_replay import PLAN,prepare,main

def setup(tmp_path):
    cache=tmp_path/"cache"
    cache.mkdir()
    sheet=tmp_path/"selected_clips.csv"
    names=[]
    for n,(_,name,category,_) in enumerate(PLAN):
        content=b"\0\0\0\x18ftypisom"+bytes([n+1])*11000
        (cache/(name+".mp4")).write_bytes(content)
        names.append({"name":name,"class":str(n),"label":category,
            "clip_start_frame0":"100","clip_end_frame0":"250",
            "event_start_frame":"121","event_end_frame":"200"})
    with sheet.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(names[0]))
        writer.writeheader()
        writer.writerows(names)
    return cache,sheet

def test_preloaded_source_manifest_is_derived_not_simulated(tmp_path):
    cache,sheet=setup(tmp_path)
    report=prepare(sheet,cache)
    assert report["model_inference_qualified"] is False
    assert report["training_centre_provenance"] is False
    assert len(report["clips"])==4
    assert report["clips"][0]["event_start_seconds"]==7.0
    assert report["clips"][-1]["event_start_seconds"] is None
    source=cache/(PLAN[0][1]+".mp4")
    assert report["clips"][0]["source_sha256"]==hashlib.sha256(source.read_bytes()).hexdigest()
    assert not (cache/"kw-research-replay.local.json").exists()

def test_reject_missing_modified_or_invalid_mp4(tmp_path):
    cache,sheet=setup(tmp_path)
    (cache/(PLAN[0][1]+".mp4")).write_bytes(b"not an mp4"*1400)
    with pytest.raises(ValueError):prepare(sheet,cache)
    (cache/(PLAN[1][1]+".mp4")).unlink()
    with pytest.raises(ValueError):prepare(sheet,cache)

def test_reject_annotation_mismatch_and_symlink(tmp_path):
    cache,sheet=setup(tmp_path)
    rows=list(csv.DictReader(sheet.open()))
    rows[0]["label"]="normal"
    with sheet.open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError):prepare(sheet,cache)
    rows[0]["label"]="covered"
    rows[0]["event_start_frame"]="9999"
    with sheet.open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError):prepare(sheet,cache)

def test_cli_never_reports_video_paths_or_drive_ids(tmp_path,monkeypatch,capsys):
    cache,sheet=setup(tmp_path)
    monkeypatch.setattr(sys,"argv",["prepare", "--selection-csv",str(sheet),
          "--clip-dir",str(cache),"--write"])
    assert main()==0
    result=json.loads(capsys.readouterr().out)
    assert result["status"]=="prepared"
    assert result["videos_copied"]==0
    assert result["source_bytes_transferred"]==0
    assert str(cache) not in json.dumps(result)
    assert (cache/"kw-research-replay.local.json").is_file()
