from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.person_detector import Detection, _nms_detections, _tile_windows


def test_tile_windows_cover_frame_with_overlap():
    windows = _tile_windows(1920, 1080, overlap=0.18)

    assert len(windows) == 4
    assert windows[0][0] == 0
    assert windows[0][1] == 0
    assert windows[-1][2] == 1920
    assert windows[-1][3] == 1080

    # Left/right and top/bottom tiles overlap, preventing a person on a split
    # boundary from disappearing solely because of the tiling strategy.
    assert windows[0][2] > windows[1][0]
    assert windows[0][3] > windows[2][1]


def test_nms_merges_duplicate_full_frame_and_tile_boxes():
    detections = [
        Detection(100, 100, 220, 360, 0.80),
        Detection(105, 105, 225, 365, 0.92),
        Detection(500, 120, 620, 370, 0.88),
    ]

    kept = _nms_detections(detections, iou_threshold=0.45)

    assert len(kept) == 2
    assert kept[0].confidence == 0.92
    assert any(item.x1 == 500 for item in kept)


def test_nms_keeps_close_but_distinct_people():
    detections = [
        Detection(100, 100, 210, 360, 0.90),
        Detection(180, 110, 300, 365, 0.89),
    ]

    kept = _nms_detections(detections, iou_threshold=0.45)

    assert len(kept) == 2
