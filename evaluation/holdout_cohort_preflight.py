"""Read-only five-pillar cohort metadata gate; never establishes model accuracy.

Preflight checks that claimed independent calibration and held-out partitions
cannot silently share source recordings, video hashes, or site/camera pairs
across *different* evaluators. Each individual pillar evaluator still owns
its own strict metric and runtime qualification. No pixels or labels are
loaded, and no private source paths appear in the output report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

PILLARS = ("attendance", "practical_activity", "camera_evidence",
           "equipment", "roi_motion")
SHA = re.compile(r"^[a-f0-9]{64}$")
ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{2,100}$")
KNOWN_INSPECTED_MARKERS = (
    "epfl", "laboratory6", "wisenet", "uhctd", "meva",
    "dod_110930728", "gnn-cca",
)
PLACEHOLDERS = ("synthetic", "example", "fixture", "placeholder", "tbd")


class PreflightError(ValueError):
    """Safe, non-identifying error category for CLI output."""


def _fail(code: str) -> None:
    raise PreflightError(code)


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _ref(base: Path, item: object, label: str) -> tuple[Path, str]:
    if (not isinstance(item, dict) or set(item) != {"path", "sha256"}
            or not isinstance(item["path"], str) or not item["path"].strip()
            or not isinstance(item["sha256"], str)
            or not SHA.fullmatch(item["sha256"])):
        _fail(label + "_invalid_reference")
    source = (base / item["path"]).resolve()
    if not source.is_file() or not source.stat().st_size:
        _fail(label + "_missing")
    if _sha(source) != item["sha256"]:
        _fail(label + "_digest_mismatch")
    return source, item["sha256"]


def _id(value: object, name: str) -> str:
    if not isinstance(value, str) or not ID.fullmatch(value):
        _fail(name + "_invalid")
    return value


def _doc(path: Path, label: str) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        _fail(label + "_invalid_json")
    if not isinstance(raw, dict):
        _fail(label + "_not_object")
    return raw


def check_cohort(path: Path, *, test_fixture: bool = False) -> dict:
    """Metadata-only split gate; safe to run without any model weights.

    test_fixture is for unit tests and always returns qualified=False.
    Real manifests return qualified=False too, because metadata alone cannot
    validate consent, blind reviewers, model inference or numerical accuracy.
    """
    path = Path(path).expanduser().resolve()
    raw = _doc(path, "cohort")
    if (raw.get("schema_version") != 1 or raw.get("status") != "frozen"
            or type(raw.get("fixture_only")) is not bool):
        _fail("cohort_schema_or_freeze_invalid")
    if raw["fixture_only"] is not bool(test_fixture):
        _fail("cohort_fixture_mode_mismatch")
    pillars = raw.get("pillars")
    if not isinstance(pillars, dict) or set(pillars) != set(PILLARS):
        _fail("five_pillar_manifest_set_incomplete")
    seen_manifest_hashes: set[str] = set()
    summaries: dict[str, dict] = {}
    group = {
        "calibration": {"recordings": set(), "digests": set(), "cameras": set()},
        "heldout": {"recordings": set(), "digests": set(), "cameras": set()},
    }
    recording_to_video: dict[str, str] = {}
    video_to_recording: dict[str, str] = {}
    recording_to_camera: dict[str, tuple[str, str]] = {}
    for pillar in PILLARS:
        manifest, manifest_sha = _ref(path.parent, pillars[pillar], "manifest")
        if manifest_sha in seen_manifest_hashes:
            _fail("duplicate_pillar_manifest")
        seen_manifest_hashes.add(manifest_sha)
        protocol = _doc(manifest, "pillar")
        if (protocol.get("schema_version") != 1 or protocol.get("status") != "frozen"
                or type(protocol.get("fixture_only")) is not bool
                or protocol["fixture_only"] is not bool(test_fixture)):
            _fail("pillar_schema_or_fixture_invalid")
        counts = {}
        for split in ("calibration", "heldout"):
            scenes = protocol.get(split)
            if not isinstance(scenes, list) or not scenes:
                _fail("pillar_partition_missing")
            seen_local_recordings: set[str] = set()
            counts[split] = len(scenes)
            for scene in scenes:
                if not isinstance(scene, dict):
                    _fail("scene_descriptor_invalid")
                recording = _id(scene.get("recording_id"), "recording_id")
                site = _id(scene.get("site_id"), "site_id")
                camera = _id(scene.get("camera_id"), "camera_id")
                _id(scene.get("scene_id"), "scene_id")
                if recording in seen_local_recordings:
                    _fail("duplicate_recording_within_pillar_partition")
                seen_local_recordings.add(recording)
                video, digest = _ref(manifest.parent, scene.get("video"), "video")
                where = (site, camera)
                if recording in recording_to_video and recording_to_video[recording] != digest:
                    _fail("recording_id_aliases_different_video")
                if digest in video_to_recording and video_to_recording[digest] != recording:
                    _fail("video_relabelled_with_different_recording_id")
                if (recording in recording_to_camera
                        and recording_to_camera[recording] != where):
                    _fail("recording_id_inconsistent_camera")
                recording_to_video[recording] = digest
                video_to_recording[digest] = recording
                recording_to_camera[recording] = where
                for key in ("source_origin", "license_basis", "privacy_basis"):
                    value = scene.get(key)
                    if not isinstance(value, str) or len(value.strip()) < 12:
                        _fail("incomplete_lawful_provenance")
                    if not test_fixture and any(w in value.lower() for w in PLACEHOLDERS):
                        _fail("placeholder_provenance")
                if split == "heldout":
                    if (scene.get("previously_inspected") is not False
                            or scene.get("blinded_review") is not True
                            or not isinstance(scene.get("reviewer_id"), str)
                            or not ID.fullmatch(scene["reviewer_id"])):
                        _fail("independent_untouched_blind_review_not_attested")
                    if not test_fixture:
                        descriptor = " ".join((
                            recording, site, camera, str(video.parent), video.name,
                            scene["source_origin"],
                        )).lower().replace(" ", "_")
                        if any(word in descriptor for word in KNOWN_INSPECTED_MARKERS):
                            _fail("known_inspected_development_source")
                bucket = group[split]
                bucket["recordings"].add(recording)
                bucket["digests"].add(digest)
                bucket["cameras"].add(where)
        summaries[pillar] = {
            "manifest_sha256": manifest_sha,
            "calibration_scenes": counts["calibration"],
            "heldout_scenes": counts["heldout"],
        }

    for kind in ("recordings", "digests", "cameras"):
        if group["calibration"][kind] & group["heldout"][kind]:
            _fail("global_calibration_holdout_" + kind + "_leakage")

    return {
        "schema_version": 1,
        "status": "metadata_preflight_passed_not_accuracy_qualified",
        "qualified": False,
        "cohort_inputs_admissible_for_individual_validation": not test_fixture,
        "fixture_only": bool(test_fixture),
        "cohort_manifest_sha256": _sha(path),
        "pillars": summaries,
        "support": {
            "calibration_recordings": len(group["calibration"]["recordings"]),
            "heldout_recordings": len(group["heldout"]["recordings"]),
            "calibration_site_camera_pairs": len(group["calibration"]["cameras"]),
            "heldout_site_camera_pairs": len(group["heldout"]["cameras"]),
        },
        "limits": [
            "Metadata-only. No numerical accuracy, identity, permission, or blindness verified.",
            "Independent reviewer and untouched source claims remain human attestations.",
            "Every individual pillar evaluator must still run actual pinned inference and pass.",
            "Public previously used footage and synthetic test fixtures cannot qualify.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Five-pillar frozen-cohort metadata preflight (never accuracy qualification)")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = check_cohort(args.manifest)
    except (PreflightError, OSError, ValueError, TypeError) as exc:
        # Do not persist exceptions containing local private paths or identifiers.
        code = str(exc) if isinstance(exc, PreflightError) else "unexpected_input_error"
        result = {"schema_version": 1, "status": "metadata_preflight_blocked",
                  "qualified": False, "reason_code": code}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["status"] != "metadata_preflight_passed_not_accuracy_qualified":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
