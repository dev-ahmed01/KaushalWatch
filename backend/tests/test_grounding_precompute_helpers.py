from pathlib import Path
import json
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.precompute_grounding_dino import (
    auto_sample_seconds,
    box_iou,
    dedupe_overlapping_boxes,
    grounding_processor_inputs,
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


def test_box_iou_reports_near_duplicate_overlap():
    iou = box_iou(
        [791.39, 555.08, 1162.25, 690.10],
        [791.99, 556.35, 1161.06, 689.01],
    )
    assert iou > 0.95


def test_dedupe_overlapping_boxes_keeps_best_score_for_synonym_duplicate():
    boxes, scores = dedupe_overlapping_boxes(
        [
            [791.39, 555.08, 1162.25, 690.10],
            [791.99, 556.35, 1161.06, 689.01],
            [100.0, 100.0, 200.0, 200.0],
        ],
        [0.5762, 0.3624, 0.41],
        iou_threshold=0.85,
    )

    assert len(boxes) == 2
    assert scores == [0.5762, 0.41]
    assert boxes[0] == [791.39, 555.08, 1162.25, 690.10]


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


class _FakeBatch(dict):
    def __init__(self, text):
        super().__init__()
        self.text = text
        self.device = None

    def to(self, device):
        self.device = device
        return self


class _NestedTextRejectingProcessor:
    def __init__(self):
        self.seen = []

    def __call__(self, *, images, text, return_tensors):
        self.seen.append(text)
        if isinstance(text, list) and text and isinstance(text[0], list):
            raise TypeError(
                "TextEncodeInput must be Union[TextInputSequence, "
                "Tuple[InputSequence, InputSequence]]"
            )
        return _FakeBatch(text)


def test_grounding_processor_inputs_falls_back_to_flat_text_on_tokenizer_shape_error():
    processor = _NestedTextRejectingProcessor()

    batch = grounding_processor_inputs(
        processor,
        image=object(),
        text="workbench. industrial work bench",
        device="cpu",
    )

    assert processor.seen == [
        [["workbench. industrial work bench"]],
        "workbench. industrial work bench",
    ]
    assert batch.text == "workbench. industrial work bench"
    assert batch.device == "cpu"


class _UnrelatedTypeErrorProcessor:
    def __call__(self, *, images, text, return_tensors):
        raise TypeError("different processor error")


def test_grounding_processor_inputs_does_not_hide_unrelated_type_error():
    with pytest.raises(TypeError, match="different processor error"):
        grounding_processor_inputs(
            _UnrelatedTypeErrorProcessor(),
            image=object(),
            text="workbench",
            device="cpu",
        )
