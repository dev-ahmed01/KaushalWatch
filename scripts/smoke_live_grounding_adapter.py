"""Actual local GroundingDINO adapter smoke using a pinned runtime snapshot.

Run only with a permitted public test image. Downloads are completed before
offline-only model setup; no private footage or secret tokens are handled.
Every model file is SHA-256 pinned and exact model revision is recorded.
This is an *inference integration check*, never accuracy qualification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.live_equipment import GroundingDinoAdapter, verify_model_snapshot

MODEL_ID = "IDEA-Research/grounding-dino-tiny"
PINNED_MODEL_REVISION = "a2bb814dd30d776dcf7e30523b00659f4f141c71"
PUBLIC_IMAGE = (
    "https://commons.wikimedia.org/wiki/Special:Redirect/file/"
    "General%20electrical%20workroom.jpg"
)
ALLOWED = {".json", ".txt", ".safetensors", ".bin", ".model", ".vocab", ".merges"}
PROMPTS = {"workbench": "workbench", "chair": "chair"}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def prepare_offline_snapshot(repo_id: str, directory: Path) -> tuple[dict[str, str], str]:
    from huggingface_hub import HfApi, snapshot_download

    revision = PINNED_MODEL_REVISION
    published = HfApi().model_info(repo_id, revision=revision)
    if published.sha != revision:
        raise RuntimeError("Pinned GroundingDINO revision is no longer available")
    snapshot = Path(snapshot_download(repo_id=repo_id, revision=revision))
    directory.mkdir(parents=True, exist_ok=False)
    pins = {}
    for file in snapshot.rglob("*"):
        if not file.is_file():
            continue
        relative = file.relative_to(snapshot)
        if relative.suffix not in ALLOWED or any(part.startswith(".") for part in relative.parts):
            continue
        destination = directory / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(file, destination)
        pins[relative.as_posix()] = digest(destination)
    verified = verify_model_snapshot(directory, pins)
    if not any(k.endswith((".bin", ".safetensors")) for k in verified):
        raise RuntimeError("Downloaded model revision contains no verified weights")
    return verified, revision


def fetch_public_image(url: str, dest: Path) -> str:
    request = Request(url, headers={"User-Agent": "KaushalWatch-public-model-smoke/1.0"})
    with urlopen(request, timeout=90) as response:
        if not str(response.headers.get("Content-Type", "")).lower().startswith("image/"):
            raise RuntimeError("Public smoke source did not return an image")
        body = response.read(15_000_001)
    if not 4_000 <= len(body) <= 15_000_000:
        raise RuntimeError("Public test image is missing or suspiciously large")
    dest.write_bytes(body)
    return digest(dest)


def run(snapshot_dir: Path, image_path: Path, out: Path, *, image_url: str) -> dict:
    import cv2

    files, revision = prepare_offline_snapshot(MODEL_ID, snapshot_dir)
    image_hash = fetch_public_image(image_url, image_path)
    frame = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if frame is None:
        raise RuntimeError("Public equipment test image cannot be decoded")
    # The model loader must be fully offline: downloading happens only
    # during the explicitly separated bootstrap above.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    adapter = GroundingDinoAdapter(
        PROMPTS, model_dir=snapshot_dir, model_files=files,
        threshold=0.35, nms_iou=0.50, device="cpu"
    )
    adapter.setup()
    detections = adapter.detect_frame(frame)
    if len(detections) != len(PROMPTS):
        raise RuntimeError("Real model did not return all requested classes")
    for proposal in detections:
        if proposal.get("proposal_status") != "unreviewed_model_proposal":
            raise RuntimeError("Real model output lost unreviewed provenance")
    assert files == verify_model_snapshot(snapshot_dir, files)
    if digest(image_path) != image_hash:
        raise RuntimeError("Public image changed during model execution")
    report = {
        "status": "real_groundingdino_local_adapter_executed",
        "qualified": False,
        "model_inference_executed": True,
        "backend": "transformers_groundingdino_cpu",
        "model_id": MODEL_ID,
        "model_revision": revision,
        "model_artifact_sha256": files,
        "test_image_url": image_url,
        "test_image_sha256": image_hash,
        "image_resolution": [int(frame.shape[1]), int(frame.shape[0])],
        "prompts": PROMPTS,
        "proposals": detections,
        "limitations": [
            "Public image single-frame smoke; not an independently annotated multi-camera evaluation",
            "Detection labels are unreviewed model proposals and may be inaccurate",
            "No attendance, equipment compliance, actual machine health or pilot accuracy is established"
        ],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"], "qualified": False,
        "revision": revision, "model_files": len(files),
        "prompts": list(PROMPTS),
        "counts": {row["label"]: row["count"] for row in detections}
    }))
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, default=Path("/tmp/kw-grounding-real"))
    parser.add_argument("--image-url", default=PUBLIC_IMAGE)
    args = parser.parse_args()
    if args.workspace.exists():
        raise SystemExit("Refusing to reuse model/image workspace from another run")
    args.workspace.mkdir(parents=True)
    run(args.workspace / "offline-model", args.workspace / "public-image.jpg",
        args.out, image_url=args.image_url)


if __name__ == "__main__":
    main()
