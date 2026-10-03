import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.person_detector import Detection
from app.services.privacy import anonymize_person_regions


def test_anonymize_person_regions_changes_only_detection_area():
    frame = np.zeros((80, 100, 3), dtype=np.uint8)
    # Structured pattern ensures blur changes pixels.
    for x in range(20, 60):
        frame[20:70, x] = (x * 3 % 255, 100, 220)

    out = anonymize_person_regions(
        frame,
        [Detection(20, 20, 60, 70, 0.9)],
        blur_kernel=11,
    )

    assert not np.array_equal(out[20:70, 20:60], frame[20:70, 20:60])
    assert np.array_equal(out[0:10, 0:10], frame[0:10, 0:10])
