"""Local-only KaushalWatch Camera Trust research CLI."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from .analysis import build_report, load_json, parse_reports
from .video import analyze_videos


def analyse(r_path: Path, s_path: Path,
            *, day3_video: Path | None = None,
            day4_video: Path | None = None,
            max_cases: int = 20,
            samples: int = 12, causal: Path | None = None):
    r, s = load_json(r_path), load_json(s_path)
    video = None
    if day3_video is not None or day4_video is not None:
        if day3_video is None or day4_video is None:
            raise ValueError("Provide BOTH Day3 and Day4 source AVI files")
        parsed = parse_reports(r, s)
        video = analyze_videos(parsed, {
            "day3": day3_video, "day4": day4_video,
        }, max_cases_per_day=max_cases, samples_per_case=samples)
    return build_report(r, s, video=video,
                        causal=load_json(causal) if causal is not None else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    ana = sub.add_parser("analyze", help="Reconcile numeric reports; optional pinned AVI sampling")
    ana.add_argument("--phase3r", type=Path, required=True)
    ana.add_argument("--phase3s", type=Path, required=True)
    ana.add_argument("--phase3p", type=Path, help="Optional bounded annotated event research context")
    ana.add_argument("--day3-video", type=Path)
    ana.add_argument("--day4-video", type=Path)
    ana.add_argument("--max-cases-per-day", type=int, default=20)
    ana.add_argument("--samples-per-case", type=int, default=12)
    ana.add_argument("--out", type=Path, required=True)
    audit = sub.add_parser("audit-video-report", help="Validate previously exported source-pinned scalar AVI evidence")
    audit.add_argument("--report", type=Path, required=True)
    audit.add_argument("--phase3r", type=Path, required=True)
    audit.add_argument("--phase3s", type=Path, required=True)
    audit.add_argument("--out", type=Path, required=True)
    conc = sub.add_parser("concordance", help="Audit and compare full AVI sparse features against research candidates")
    conc.add_argument("--full-report", type=Path, required=True)
    conc.add_argument("--previous-report", type=Path)
    conc.add_argument("--phase3r", type=Path, required=True)
    conc.add_argument("--phase3s", type=Path, required=True)
    conc.add_argument("--out", type=Path, required=True)
    clips = sub.add_parser("clip-evaluate", help="Numerically benchmark source-labeled short Drive clips")
    clips.add_argument("--manifest", type=Path, required=True)
    clips.add_argument("--clip-dir", type=Path, required=True)
    clips.add_argument("--stride", type=int, default=3)
    clips.add_argument("--out", type=Path, required=True)
    accepted = sub.add_parser("product-readiness", help="Validate all source pins and produce derived acceptance ledger")
    accepted.add_argument("--phase3r", required=True, type=Path)
    accepted.add_argument("--phase3s", required=True, type=Path)
    accepted.add_argument("--report", required=True, type=Path)
    accepted.add_argument("--concordance", required=True, type=Path)
    accepted.add_argument("--clips", required=True, type=Path)
    accepted.add_argument("--drive-manifest", required=True, type=Path)
    accepted.add_argument("--clip-manifest", required=True, type=Path)
    accepted.add_argument("--out", required=True, type=Path)
    ex = sub.add_parser("probe-unlabeled-scenes",help="Apply predeclared fixed-time sparse sampling to unannotated videos")
    ex.add_argument('--videos',type=Path,nargs='+',required=True)
    ex.add_argument('--seconds',type=float,default=5)
    ex.add_argument('--max-samples',type=int,default=120)
    ex.add_argument('--out',type=Path,required=True)
    serve = sub.add_parser("serve", help="Serve read-only localhost research dashboard")
    serve.add_argument("--report", type=Path, required=True)
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--concordance", type=Path)
    serve.add_argument("--clip-report", type=Path)
    args = parser.parse_args()
    if args.action == "analyze":
        result = analyse(args.phase3r, args.phase3s,
                         day3_video=args.day3_video, day4_video=args.day4_video,
                         max_cases=args.max_cases_per_day,
                         samples=args.samples_per_case, causal=args.phase3p)
        if args.out.exists():
            parser.error("Choose a new output file; no research file overwrite permitted")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2, sort_keys=True, allow_nan=False)
            f.write("\n")
        print(json.dumps({"status": result["status"],
                          "windows": result["number_of_windows"],
                          "video_evidence_available": result["recordings_available_in_workspace"],
                          "report": str(args.out)}, indent=2))
    elif args.action == "audit-video-report":
        from .audit import audit_video_report
        result = audit_video_report(load_json(args.report), load_json(args.phase3r), load_json(args.phase3s))
        if args.out.exists():
            parser.error("Choose a NEW unused output path for research audit")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2, sort_keys=True, allow_nan=False)
            f.write("\n")
        print(json.dumps({"status": result["status"], "measured_windows": result["measured_video_windows"],
                          "unmeasured_windows": result["unmeasured_video_windows"],
                          "report": str(args.out)}, indent=2))
    elif args.action == "concordance":
        from .concordance import diagnose
        result = diagnose(
            load_json(args.full_report), load_json(args.phase3r),
            load_json(args.phase3s),
            load_json(args.previous_report) if args.previous_report is not None else None,
        )
        if args.out.exists():
            parser.error("Output must be a NEW unused JSON report")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2, sort_keys=True, allow_nan=False)
            f.write("\n")
        print(json.dumps({"status": result["status"], "window_count": result["window_count"],
                          "concordance": result["overall_concordance"],
                          "physical_ground_truth_available": False,
                          "report": str(args.out)}, indent=2))
    elif args.action == "clip-evaluate":
        from .clip_engine import evaluate_directory
        result = evaluate_directory(args.manifest, args.clip_dir, args.out, stride=args.stride)
        print(json.dumps({"status":result["status"],"clips_evaluated":result["clips_evaluated"],
                          "missing":result["missing"],"research_only":True,"report":str(args.out)},indent=2))
    elif args.action == 'probe-unlabeled-scenes':
        from .external_probe import run
        result=run(args.videos,args.out,interval=args.seconds,max_samples=args.max_samples)
        print(json.dumps({'status':result['status'],
                          'unlabeled_context_videos':len(result['videos']),
                          'frames_measured':result['total_frames_decoded'],
                          'production_qualified':False},indent=2))
    elif args.action == 'product-readiness':
        from .product_readiness import generate, save_atomic
        result=generate(load_json(args.phase3r),load_json(args.phase3s),
                        load_json(args.report),load_json(args.concordance),
                        load_json(args.clips),args.drive_manifest,args.clip_manifest)
        save_atomic(result,args.out)
        print(json.dumps({'status':result['status'],
                          'software_readiness':result['software_readiness'],
                          'production_release':result['production_release'],
                          'output':str(args.out)},indent=2))
    else:
        import uvicorn
        from .server import create_app
        uvicorn.run(create_app(args.report, args.concordance, args.clip_report), host="127.0.0.1", port=args.port,
                    log_level="warning")

if __name__ == "__main__":
    main()
