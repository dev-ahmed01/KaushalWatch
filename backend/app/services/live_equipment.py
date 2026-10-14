"""Optional live GroundingDINO inference with explicit offline artifact integrity.

Do not import torch or transformers in the core attendance/API path.
A missing checkpoint or model exception is NEVER converted into zero equipment.
Results are raw, unreviewed proposals, not compliance decisions.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import cv2


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def verify_model_snapshot(directory: Path, digests: dict[str, str]) -> dict[str, str]:
    directory = Path(directory).expanduser().resolve()
    if not directory.is_dir() or not isinstance(digests, dict) or not digests:
        raise ValueError("An offline model directory and pinned artifact digests are required")
    found = {}
    for key, wanted in digests.items():
        if (not isinstance(key, str) or not key or Path(key).is_absolute()
            or any(part in ("..", ".") for part in Path(key).parts)
            or not isinstance(wanted, str) or len(wanted) != 64
            or any(c not in "0123456789abcdef" for c in wanted)):
            raise ValueError("Unsafe or invalid model artifact pin")
        target = (directory / key).resolve()
        if not target.is_relative_to(directory) or not target.is_file() or not target.stat().st_size:
            raise ValueError("Pinned model artifact is absent or escapes its snapshot")
        actual = _hash_file(target)
        if actual != wanted:
            raise ValueError("Pinned model snapshot SHA-256 mismatch")
        found[key] = actual
    checkpoint = [key for key in digests if key.endswith((".safetensors", ".bin"))]
    if not checkpoint:
        raise ValueError("Model snapshot has no pinned weight checkpoint")
    # The loader must not be able to consume unpinned files, alternate
    # checkpoints, extra tokenizer configs or untrusted Python modules.
    existing = {
        str(path.relative_to(directory)).replace("\\", "/")
        for path in directory.rglob("*") if path.is_file()
    }
    if existing != set(found):
        raise ValueError("Unpinned file in model snapshot")
    if any(key.endswith(".py") for key in found):
        raise ValueError("Remote model code is not accepted for private inference")
    return found


def _processor_inputs(processor, image, prompt: str, device: str):
    # Match the reviewed offline precompute path, including Windows tokenizer
    # fallback only for the recognized TextEncodeInput compatibility issue.
    try:
        batch = processor(images=image, text=[[prompt]], return_tensors="pt")
    except TypeError as exc:
        if "TextEncodeInput" not in str(exc):
            raise
        batch = processor(images=image, text=prompt, return_tensors="pt")
    return batch.to(device)


def _nms(boxes: list[list[float]], scores: list[float], iou: float) -> list[int]:
    """Stable per-item overlap suppression to avoid counting one object twice."""
    order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
    keep = []
    while order:
        i = order.pop(0)
        keep.append(i)
        x1, y1, x2, y2 = boxes[i]
        remaining = []
        for j in order:
            a, b, c, d = boxes[j]
            intersection = max(0.0, min(x2, c) - max(x1, a)) * max(0.0, min(y2, d) - max(y1, b))
            area1 = (x2-x1)*(y2-y1)
            area2 = (c-a)*(d-b)
            overlap = intersection/(area1+area2-intersection) if area1+area2-intersection > 0 else 0.0
            if overlap <= iou:
                remaining.append(j)
        order = remaining
    return keep


def validate_detections(boxes: list, scores: list, width: int, height: int,
                        *, nms_iou: float = 0.5) -> dict:
    if (not isinstance(boxes, list) or not isinstance(scores, list)
        or len(boxes) != len(scores) or len(boxes) > 2500
        or width < 1 or height < 1 or not 0 < nms_iou < 1):
        raise ValueError("Invalid equipment detector output dimensions")
    clean_boxes = []
    clean_scores = []
    for box, raw in zip(boxes, scores):
        if (not isinstance(box, (tuple, list)) or len(box) != 4
            or any(type(v) not in (float, int) or not math.isfinite(v) for v in box)
            or type(raw) not in (float, int) or not math.isfinite(raw) or not 0 <= raw <= 1):
            raise ValueError("GroundingDINO produced invalid coordinates/confidence")
        x1, y1, x2, y2 = [float(v) for v in box]
        # Reject corrupt out-of-image predictions rather than inventing boxes.
        if x1 < -1 or y1 < -1 or x2 > width+1 or y2 > height+1 or x2 <= x1 or y2 <= y1:
            raise ValueError("GroundingDINO produced an invalid bounding box")
        clean_boxes.append([max(0.0,x1), max(0.0,y1), min(float(width),x2), min(float(height),y2)])
        clean_scores.append(float(raw))
    keep = _nms(clean_boxes, clean_scores, nms_iou)
    filtered_scores = [round(clean_scores[i], 4) for i in keep]
    return {
        "count": len(keep), "model_count": len(keep),
        "confidence": round(sum(filtered_scores)/len(keep),4) if keep else 0.0,
        "boxes": [[round(v, 2) for v in clean_boxes[i]] for i in keep],
        "scores": filtered_scores,
    }


class GroundingDinoAdapter:
    """Live frame/video inference using a locally SHA-pinned model snapshot.

    `setup` never downloads weights or invokes remote model code.
    A `detect_at` call is only valid after `bind_video`; every output is
    explicitly an unreviewed model proposal.
    """

    def __init__(self, prompts: dict[str, str], *, model_dir: Path,
                 model_files: dict[str, str], threshold: float = 0.35,
                 device: str = "cpu", nms_iou: float = 0.5):
        if (not isinstance(prompts, dict) or not 1 <= len(prompts) <= 24
            or any(not isinstance(k, str) or not k.replace("_","").isalnum()
                   or not isinstance(v, str) or not 2 <= len(v.strip()) <= 200
                   for k, v in prompts.items())):
            raise ValueError("GroundingDINO item prompts must be a reviewed ID/text mapping")
        if (type(threshold) not in (int, float) or not 0 < threshold < 1
            or device not in {"cpu", "cuda"} or not 0 < nms_iou < 1):
            raise ValueError("Invalid explicit detector threshold, device or NMS setting")
        self.prompts = dict(prompts)
        self.model_dir = Path(model_dir)
        self.model_files = dict(model_files)
        self.threshold = float(threshold)
        self.device = device
        self.nms_iou = float(nms_iou)
        self._processor = self._model = self._torch = None
        self._cap = None
        self._source_digest = None

    def setup(self) -> None:
        verify_model_snapshot(self.model_dir, self.model_files)
        try:
            import torch
            from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection
        except ImportError as exc:
            raise RuntimeError("Optional torch/transformers equipment environment not installed") from exc
        if self.device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("Requested CUDA equipment inference is not available")
        self._processor = AutoProcessor.from_pretrained(
            str(self.model_dir), local_files_only=True, trust_remote_code=False)
        self._model = AutoModelForZeroShotObjectDetection.from_pretrained(
            str(self.model_dir), local_files_only=True, trust_remote_code=False
        ).to(self.device)
        self._model.eval()
        self._torch = torch
        # A model loader must not have modified any pinned files.
        verify_model_snapshot(self.model_dir, self.model_files)

    def detect_frame(self, frame) -> list[dict]:
        if self._model is None or self._processor is None:
            raise RuntimeError("Uninitialized equipment detector; predictions are unavailable")
        import numpy as np
        from PIL import Image
        if (not isinstance(frame, np.ndarray) or frame.ndim != 3
            or frame.shape[2] != 3 or frame.dtype != np.uint8
            or frame.shape[0] < 2 or frame.shape[1] < 2):
            raise ValueError("Equipment detector requires a decoded uint8 BGR frame")
        image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        predictions = []
        for item_id, prompt in self.prompts.items():
            batch = _processor_inputs(self._processor, image, prompt, self.device)
            with self._torch.no_grad():
                out = self._model(**batch)
            result = self._processor.post_process_grounded_object_detection(
                out, batch.input_ids, threshold=self.threshold,
                text_threshold=self.threshold,
                target_sizes=[(image.height, image.width)]
            )[0]
            boxes = result["boxes"].detach().cpu().tolist()
            scores = result["scores"].detach().cpu().tolist()
            summary = validate_detections(boxes, scores, image.width, image.height,
                                          nms_iou=self.nms_iou)
            predictions.append({
                "label": item_id, "prompt": prompt, **summary,
                "proposal_status": "unreviewed_model_proposal",
            })
        return predictions

    def bind_video(self, source: Path, sha256: str) -> None:
        if not isinstance(sha256, str) or len(sha256) != 64:
            raise ValueError("Video binding requires SHA-256")
        source = Path(source).resolve()
        if not source.is_file() or _hash_file(source) != sha256:
            raise ValueError("Source recording changed before live inference")
        self.close()
        self._cap = cv2.VideoCapture(str(source))
        if not self._cap.isOpened():
            self.close()
            raise ValueError("Cannot decode pinned equipment recording")
        self._source_digest = (source, sha256)

    def detect_at(self, second: float) -> list[dict]:
        if (self._cap is None or self._source_digest is None or type(second) not in (int,float)
            or not math.isfinite(second) or second < 0):
            raise RuntimeError("GroundingDINO requires a pinned open video and valid timestamp")
        source, expected = self._source_digest
        # Before EACH call, verify the source has not changed after binding.
        if _hash_file(source) != expected:
            raise ValueError("Source video modified during equipment inference")
        self._cap.set(cv2.CAP_PROP_POS_MSEC, second * 1000.0)
        ok, frame = self._cap.read()
        if not ok:
            raise RuntimeError("Pinned equipment frame unavailable (no zero-count fallback)")
        return self.detect_frame(frame)

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
        self._cap = None
        self._source_digest = None
