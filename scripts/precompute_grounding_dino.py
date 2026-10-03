from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
from PIL import Image
import torch
from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

MODEL_ID = "IDEA-Research/grounding-dino-tiny"

DEFAULT_PROMPTS = {
    "workbench": "a workbench",
    "chair": "a training chair",
    "training_panel": "an electrical training panel",
    "drill_machine": "a drill machine",
}


def read_frame(video: cv2.VideoCapture, second: float):
    video.set(cv2.CAP_PROP_POS_MSEC, second * 1000.0)
    ok, frame = video.read()
    if not ok:
        raise RuntimeError(f"Could not read frame at {second:.2f}s")
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def detect_prompt(processor, model, device, image: Image.Image, prompt: str, threshold: float):
    text_labels = [[prompt]]
    inputs = processor(images=image, text=text_labels, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model(**inputs)

    result = processor.post_process_grounded_object_detection(
        outputs,
        threshold=threshold,
        text_threshold=threshold,
        target_sizes=[(image.height, image.width)],
    )[0]

    scores = [float(x) for x in result["scores"].detach().cpu().tolist()]
    boxes = [
        [round(float(v), 2) for v in box]
        for box in result["boxes"].detach().cpu().tolist()
    ]
    return {
        "count": len(boxes),
        "confidence": round(sum(scores) / len(scores), 4) if scores else 0.0,
        "boxes": boxes,
        "scores": [round(x, 4) for x in scores],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Offline GroundingDINO precompute for the KaushalWatch detector-cache adapter."
    )
    parser.add_argument("--video", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--seconds", default="0,10,20", help="Comma-separated sample timestamps")
    parser.add_argument("--threshold", type=float, default=0.35)
    parser.add_argument("--model-id", default=MODEL_ID)
    parser.add_argument("--device", default=None, help="cuda, cpu, mps; auto-selects when omitted")
    args = parser.parse_args()

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    processor = AutoProcessor.from_pretrained(args.model_id)
    model = AutoModelForZeroShotObjectDetection.from_pretrained(args.model_id).to(device)
    model.eval()

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise SystemExit(f"Could not open video: {args.video}")

    rows = []
    try:
        for second in [float(x.strip()) for x in args.seconds.split(",") if x.strip()]:
            rgb = read_frame(cap, second)
            image = Image.fromarray(rgb)
            detections = []
            for item_id, prompt in DEFAULT_PROMPTS.items():
                result = detect_prompt(processor, model, device, image, prompt, args.threshold)
                detections.append({
                    "label": item_id,
                    "prompt": prompt,
                    **result,
                })
            rows.append({"second": second, "detections": detections})
    finally:
        cap.release()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2))
    print(out)
    print(
        "Precompute complete. Inspect detections visually before using this cache in the demo; "
        "zero-shot confidence is not itself a compliance decision."
    )


if __name__ == "__main__":
    main()
