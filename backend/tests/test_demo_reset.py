import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.reset_demo_state import reset_demo_state


def test_demo_reset_only_clears_mutable_runtime_state(tmp_path):
    data = tmp_path / "data"
    evidence = data / "evidence"
    raw = data / "raw"
    evidence.mkdir(parents=True)
    raw.mkdir(parents=True)

    for name in (
        "cases.json",
        "analysis_history.json",
        "centre_settings.json",
        "edge_events.json",
        "evidence_index.json",
    ):
        (data / name).write_text("[]")

    (evidence / "frame.jpg").write_bytes(b"evidence")
    (raw / "demo.mp4").write_bytes(b"raw-video")
    (data / "README.md").write_text("keep me")

    result = reset_demo_state(data)

    assert result["removed"]
    assert not (data / "cases.json").exists()
    assert not (evidence / "frame.jpg").exists()
    assert (raw / "demo.mp4").read_bytes() == b"raw-video"
    assert (data / "README.md").read_text() == "keep me"
