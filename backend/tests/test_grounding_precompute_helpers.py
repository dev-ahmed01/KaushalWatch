from pathlib import Path
import json
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.precompute_grounding_dino import (
    auto_sample_seconds,
    load_prompts,
    parse_sample_seconds,
)


def test_auto_sample_seconds_stays_inside_short_clip():
    seconds = auto_sample_seconds(6.946, sample_count=5)

    assert len(seconds) == 5
    assert seconds[0] == 0.0
    assert seconds[-1] < 6.946
    assert seconds == sorted(seconds)


def test_parse_sample_seconds_rejects_out_of_bounds_timestamp():
    with pytest.raises(ValueError, match="outside video bounds"):
        parse_sample_seconds(
            "0,10,20",
            duration_seconds=6.946,
            sample_count=5,
        )


def test_parse_sample_seconds_auto_uses_requested_count():
    seconds = parse_sample_seconds(
        "auto",
        duration_seconds=11.279,
        sample_count=4,
    )

    assert len(seconds) == 4
    assert seconds[-1] < 11.279


def test_load_prompts_accepts_manifest_item_mapping(tmp_path):
    path = tmp_path / "prompts.json"
    path.write_text(
        json.dumps(
            {
                "workbench": "industrial work table",
                "training_panel": "electrical control panel",
            }
        ),
        encoding="utf-8",
    )

    prompts = load_prompts(str(path))

    assert prompts["workbench"] == "industrial work table"
    assert prompts["training_panel"] == "electrical control panel"
