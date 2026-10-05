from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

MODEL_ID = "IDEA-Research/grounding-dino-tiny"

DEFAULT_PROMPTS = {
    "workbench": "workbench. work table. industrial work bench",
    "chair": "chair. stool. seat",
    "training_panel": "electrical control panel. electrical switchboard. training panel",
    "drill_machine": "drill machine. drilling machine. power drill",
}


def video_metadata(video: cv2.VideoCapture) -> dict:
    fps = float(video.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = int(video.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    duration = (frame_count / fps) if fps > 0 and frame_count > 0 else 0.0
    return {
        "fps": fps,
        "frame_count": frame_count,
        "width": width,
        "height": height,
        "duration_seconds": duration,
    }


def auto_sample_seconds(duration_seconds: float, sample_count: int = 5) -> list[float]:
    """Return evenly spaced in-bounds timestamps for short or long demo clips."""

    if duration_seconds <= 0:
        raise ValueError("Video duration must be known for automatic sampling")
    if sample_count < 1:
        raise ValueError("sample_count must be >= 1")

    # Avoid the exact final frame, which can be unreadable for some codecs.
    end = max(0.0, duration_seconds - min(0.15, duration_seconds * 0.02))
    if sample_count == 1 or end <= 0:
        return [0.0]

    return [
        round((end * index) / (sample_count - 1), 3)
        for index in range(sample_count)
    ]


def parse_sample_seconds(
    raw: str,
    *,
    duration_seconds: float,
    sample_count: int,
) -> list[float]:
    if raw.strip().lower() == "auto":
        return auto_sample_seconds(duration_seconds, sample_count)

    seconds = [float(value.strip()) for value in raw.split(",") if value.strip()]
    if not seconds:
        raise ValueError("Provide at least one sample timestamp or use --seconds auto")

    invalid = [
        second
        for second in seconds
        if second < 0 or (duration_seconds > 0 and second >= duration_seconds)
    ]
    if invalid:
        raise ValueError(
            "Sample timestamp(s) outside video bounds: "
            + ", ".join(f"{value:g}" for value in invalid)
            + (
                f" (duration={duration_seconds:.3f}s)"
                if duration_seconds > 0
                else ""
            )
        )
    return seconds


def load_prompts(path: str | None) -> dict[str, str]:
    if not path:
        return dict(DEFAULT_PROMPTS)

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not payload:
        raise ValueError("Prompt config must be a non-empty JSON object")

    prompts: dict[str, str] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("Prompt config values must map string item IDs to strings")
        key = key.strip()
        value = value.strip()
        if not key or not value:
            raise ValueError("Prompt config item IDs and prompts must be non-empty")
        prompts[key] = value
    return prompts


def read_frame(video: cv2.VideoCapture, second: float):
    video.set(cv2.CAP_PROP_POS_MSEC, second * 1000.0)
    ok, frame = video.read()
    if not ok:
        raise RuntimeError(f"Could not read frame at {second:.2f}s")
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def grounding_processor_inputs(processor, image, text, device):
    """Encode GroundingDINO text across Transformers/tokenizers compatibility variants.

    Current Transformers docs allow nested label lists, but some Windows/tokenizers
    combinations reject that shape with TextEncodeInput TypeError. Prefer the documented
    nested shape and fall back to a period-separated string only for that specific error.
    """

    if isinstance(text, str):
        documented_text = [[text]]
        fallback_text = text
    else:
        labels = [str(value).strip() for value in text if str(value).strip()]
        documented_text = [labels]
        fallback_text = ". ".join(value.rstrip(".") for value in labels)
        if fallback_text and not fallback_text.endswith("."):
            fallback_text += "."

    try:
        return processor(
            images=image,
            text=documented_text,
            return_tensors="pt",
        ).to(device)
    except TypeError as exc:
        if "TextEncodeInput" not in str(exc):
            raise
        return processor(
            images=image,
            text=fallback_text,
            return_tensors="pt",
        ).to(device)


def detect_prompt(
    processor,
    model,
    torch_module,
    device,
    image,
    prompt: str,
    threshold: float,
):
    inputs = grounding_processor_inputs(processor, image, prompt, device)
    with torch_module.no_grad():
        outputs = model(**inputs)

    result = processor.post_process_grounded_object_detection(
        outputs,
        inputs.input_ids,
        threshold=threshold,
        text_threshold=threshold,
        target_sizes=[(image.height, image.width)],
    )[0]

    scores = [float(x) for x in result["scores"].detach().cpu().tolist()]
    boxes = [
        [round(float(value), 2) for value in box]
        for box in result["boxes"].detach().cpu().tolist()
    ]
    return {
        "count": len(boxes),
        "confidence": round(sum(scores) / len(scores), 4) if scores else 0.0,
        "boxes": boxes,
        "scores": [round(value, 4) for value in scores],
    }


def render_review_image(image, detections: list[dict], out_path: Path, second: float) -> None:
    from PIL import ImageDraw

    review = image.copy()
    draw = ImageDraw.Draw(review)
    draw.rectangle((0, 0, review.width, 34), fill=(0, 0, 0))
    draw.text((10, 10), f"KaushalWatch equipment review | t={second:.2f}s", fill=(255, 255, 255))

    for detection in detections:
        label = detection["label"]
        scores = detection.get("scores", [])
        for index, box in enumerate(detection.get("boxes", [])):
            x1, y1, x2, y2 = [float(value) for value in box]
            score = scores[index] if index < len(scores) else 0.0
            draw.rectangle((x1, y1, x2, y2), outline=(255, 215, 0), width=3)
            caption = f"{label} {score:.2f}"
            top = max(35.0, y1 - 18.0)
            draw.rectangle((x1, top, min(review.width, x1 + 150), top + 18), fill=(0, 0, 0))
            draw.text((x1 + 3, top + 2), caption, fill=(255, 255, 255))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    review.save(out_path, quality=92)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Offline GroundingDINO precompute for the KaushalWatch equipment-cache "
            "adapter, with review images for human validation."
        )
    )
    parser.add_argument("--video", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--seconds",
        default="auto",
        help="Comma-separated sample timestamps or 'auto' (default).",
    )
    parser.add_argument(
        "--sample-count",
        type=int,
        default=5,
        help="Number of evenly spaced frames when --seconds auto is used.",
    )
    parser.add_argument("--threshold", type=float, default=0.35)
    parser.add_argument("--model-id", default=MODEL_ID)
    parser.add_argument("--device", default=None, help="cuda, cpu, mps; auto-selects when omitted")
    parser.add_argument(
        "--prompt-config",
        default=None,
        help="Optional JSON mapping manifest item IDs to GroundingDINO prompts.",
    )
    parser.add_argument(
        "--review-dir",
        default=None,
        help="Directory for annotated review JPGs; defaults beside --out.",
    )
    args = parser.parse_args()

    if not 0 < args.threshold < 1:
        raise SystemExit("--threshold must be between 0 and 1")

    # Heavy optional dependencies stay outside the core KaushalWatch runtime.
    try:
        import torch
        from PIL import Image
        from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor
    except ImportError as exc:
        raise SystemExit(
            "GroundingDINO optional dependencies are missing. Install an appropriate "
            "PyTorch build, then run: pip install -r backend/requirements-grounding.txt"
        ) from exc

    prompts = load_prompts(args.prompt_config)
    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    processor = AutoProcessor.from_pretrained(args.model_id)
    model = AutoModelForZeroShotObjectDetection.from_pretrained(args.model_id).to(device)
    model.eval()

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise SystemExit(f"Could not open video: {args.video}")

    metadata = video_metadata(cap)
    try:
        seconds = parse_sample_seconds(
            args.seconds,
            duration_seconds=metadata["duration_seconds"],
            sample_count=args.sample_count,
        )
    except ValueError as exc:
        cap.release()
        raise SystemExit(str(exc)) from exc

    out = Path(args.out)
    review_dir = (
        Path(args.review_dir)
        if args.review_dir
        else out.parent / f"{out.stem}-review"
    )

    rows = []
    try:
        for sample_index, second in enumerate(seconds):
            rgb = read_frame(cap, second)
            image = Image.fromarray(rgb)
            detections = []
            for item_id, prompt in prompts.items():
                result = detect_prompt(
                    processor,
                    model,
                    torch,
                    device,
                    image,
                    prompt,
                    args.threshold,
                )
                detections.append(
                    {
                        "label": item_id,
                        "prompt": prompt,
                        **result,
                    }
                )

            rows.append({"second": second, "detections": detections})
            render_review_image(
                image,
                detections,
                review_dir / f"{sample_index:02d}-{second:.3f}s.jpg",
                second,
            )
            counts = ", ".join(
                f"{item['label']}={item['count']}" for item in detections
            )
            print(f"t={second:.3f}s | {counts}")
    finally:
        cap.release()

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    meta_path = out.with_suffix(out.suffix + ".meta.json")
    meta_path.write_text(
        json.dumps(
            {
                "video": str(Path(args.video).expanduser().resolve()),
                "model_id": args.model_id,
                "device": device,
                "threshold": args.threshold,
                "prompts": prompts,
                "video_metadata": metadata,
                "sample_seconds": seconds,
                "cache_path": str(out),
                "review_dir": str(review_dir),
                "claim_boundary": (
                    "Zero-shot detections require human review before promotion to the "
                    "stage-safe cache. Detection confidence is not a compliance decision."
                ),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\nCache: {out}")
    print(f"Metadata: {meta_path}")
    print(f"Review images: {review_dir}")
    print(
        "Precompute complete. Inspect every review image before using this cache in "
        "the demo; zero-shot confidence is not itself a compliance decision."
    )


if __name__ == "__main__":
    main()
