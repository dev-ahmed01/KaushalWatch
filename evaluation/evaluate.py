from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path


def safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="KaushalWatch compliance evaluation")
    parser.add_argument("--input", required=True, help="CSV with true_count,pred_count,true_issue,pred_issue")
    parser.add_argument("--out-dir", default="evaluation/output")
    args = parser.parse_args()
    rows = list(csv.DictReader(Path(args.input).open()))
    if not rows:
        raise SystemExit("No rows in evaluation CSV")
    abs_errors = []
    tp = fp = fn = tn = 0
    for r in rows:
        true_count, pred_count = int(r["true_count"]), int(r["pred_count"])
        abs_errors.append(abs(true_count - pred_count))
        true_issue = str(r["true_issue"]).strip().lower() in {"1","true","yes"}
        pred_issue = str(r["pred_issue"]).strip().lower() in {"1","true","yes"}
        if true_issue and pred_issue: tp += 1
        elif not true_issue and pred_issue: fp += 1
        elif true_issue and not pred_issue: fn += 1
        else: tn += 1
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    f1 = safe_div(2 * precision * recall, precision + recall)
    metrics = {
        "samples": len(rows),
        "occupancy_mae": sum(abs_errors) / len(abs_errors),
        "compliance_cases": {"tp":tp,"fp":fp,"fn":fn,"tn":tn},
        "alert_precision": precision,
        "alert_recall": recall,
        "alert_f1": f1,
        "false_positive_rate": safe_div(fp, fp + tn),
        "false_negative_rate": safe_div(fn, fn + tp),
        "warning": "Valid only for the supplied annotated demonstration dataset."
    }
    out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
    (out/"evaluation_report.json").write_text(json.dumps(metrics, indent=2))
    with (out/"evaluation_summary.csv").open("w", newline="") as f:
        w = csv.writer(f); w.writerow(["metric","value"])
        for k,v in metrics.items():
            if not isinstance(v,dict): w.writerow([k,v])
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
