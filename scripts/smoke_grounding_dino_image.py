from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen
import shutil

from PIL import Image
import torch
from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor


DEFAULT_IMAGE_URL = (
    "https://commons.wikimedia.org/wiki/Special:Redirect/file/"
    "General%20electrical%20workroom.jpg"
)
MODEL_ID = "IDEA-Research/grounding-dino-tiny"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-url", default=DEFAULT_IMAGE_URL)
    parser.add_argument("--image", default="/tmp/kaushalwatch-grounding-smoke.jpg")
    parser.add_argument("--out", default="/tmp/kaushalwatch-grounding-smoke.json")
    parser.add_argument("--threshold", type=float, default=0.30)
    parser.add_argument(
        "--prompts",
        default="a workbench,a training chair,an electrical training panel,a drill machine",
    )
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        image_path.parent.mkdir(parents=True, exist_ok=True)
        request = Request(
            args.image_url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; KaushalWatch-SIH/1.0; research prototype)"
            },
        )
        with urlopen(request, timeout=60) as response, image_path.open("wb") as out:
            shutil.copyfileobj(response, out)

    image = Image.open(image_path).convert("RGB")
    labels = [x.strip() for x in args.prompts.split(",") if x.strip()]
    device = "cuda" if torch.cuda.is_available() else "cpu"

    processor = AutoProcessor.from_pretrained(MODEL_ID)
    model = AutoModelForZeroShotObjectDetection.from_pretrained(MODEL_ID).to(device)
    model.eval()

    inputs = processor(images=image, text=[labels], return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model(**inputs)

    result = processor.post_process_grounded_object_detection(
        outputs,
        inputs.input_ids,
        threshold=args.threshold,
        text_threshold=args.threshold,
        target_sizes=[image.size[::-1]],
    )[0]

    payload = {
        "model": MODEL_ID,
        "source_image": args.image_url,
        "source_license": "CC0 1.0",
        "threshold": args.threshold,
        "detections": [
            {
                "label": str(label),
                "score": round(float(score), 4),
                "box": [round(float(v), 2) for v in box.tolist()],
            }
            for box, score, label in zip(
                result["boxes"],
                result["scores"],
                result.get("text_labels", result["labels"]),
            )
        ],
        "interpretation": (
            "Smoke-test only. These detections are not compliance evidence or final accuracy."
        ),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
