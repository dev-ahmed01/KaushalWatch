from __future__ import annotations

import cv2
import numpy as np

from app.services.person_detector import Detection


def anonymize_person_regions(
    frame: np.ndarray,
    detections: list[Detection],
    *,
    blur_kernel: int = 31,
) -> np.ndarray:
    """Blur detected person regions before central evidence retention.

    This is evidence minimization, not a biometric transformation. No identity or
    embedding is produced. Detection coordinates are used only for this frame.
    """
    output = frame.copy()
    kernel = max(3, blur_kernel)
    if kernel % 2 == 0:
        kernel += 1

    h, w = output.shape[:2]
    for det in detections:
        x1 = max(0, min(w - 1, int(det.x1)))
        y1 = max(0, min(h - 1, int(det.y1)))
        x2 = max(x1 + 1, min(w, int(det.x2)))
        y2 = max(y1 + 1, min(h, int(det.y2)))
        roi = output[y1:y2, x1:x2]
        if roi.size == 0:
            continue
        output[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (kernel, kernel), 0)
        cv2.rectangle(output, (x1, y1), (x2, y2), (255, 255, 255), 2)
    return output
