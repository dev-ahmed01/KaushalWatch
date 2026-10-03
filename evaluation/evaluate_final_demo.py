from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def read_csv(path: str) -> list[dict[str, str]]:
    rows = list(csv.DictReader(Path(path).open()))
    if not rows:
        raise ValueError(f"No rows in {path}")
    return rows


def to_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def classification_metrics(tp: int, fp: int, fn: int, tn: int) -> dict:
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    f1 = safe_div(2 * precision * recall, precision + recall)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positive_rate": safe_div(fp, fp + tn),
        "false_negative_rate": safe_div(fn, fn + tp),
    }


def attendance_metrics(rows: list[dict[str, str]]) -> dict:
    errors: list[int] = []
    tp = fp = fn = tn = 0
    for row in rows:
        true_count = int(row["true_count"])
        pred_count = int(row["pred_count"])
        errors.append(abs(true_count - pred_count))
        truth = to_bool(row["true_issue"])
        pred = to_bool(row["pred_issue"])
        if truth and pred:
            tp += 1
        elif not truth and pred:
            fp += 1
        elif truth and not pred:
            fn += 1
        else:
            tn += 1
    return {
        "samples": len(rows),
        "occupancy_mae": sum(errors) / len(errors),
        "max_count_error": max(errors),
        "attendance_case_detection": classification_metrics(tp, fp, fn, tn),
    }


def equipment_metrics(rows: list[dict[str, str]]) -> dict:
    per_item: dict[str, list[int]] = defaultdict(list)
    all_errors: list[int] = []
    exact = 0
    under = 0
    over = 0
    for row in rows:
        item = row["item_id"]
        true_count = int(row["true_count"])
        pred_count = int(row["pred_count"])
        error = abs(true_count - pred_count)
        per_item[item].append(error)
        all_errors.append(error)
        if pred_count == true_count:
            exact += 1
        elif pred_count < true_count:
            under += 1
        else:
            over += 1

    return {
        "samples": len(rows),
        "count_mae": sum(all_errors) / len(all_errors),
        "exact_count_rate": exact / len(rows),
        "under_count_rate": under / len(rows),
        "over_count_rate": over / len(rows),
        "per_item_count_mae": {
            item: sum(errors) / len(errors)
            for item, errors in sorted(per_item.items())
        },
    }


def operability_metrics(rows: list[dict[str, str]]) -> dict:
    correct = 0
    evaluated = 0
    uncertain = 0
    for row in rows:
        truth = row["true_state"].strip().upper()
        pred = row["pred_state"].strip().upper()
        if pred == "UNCERTAIN":
            uncertain += 1
            continue
        evaluated += 1
        if pred == truth:
            correct += 1
    return {
        "samples": len(rows),
        "evaluated_samples": evaluated,
        "uncertain_samples": uncertain,
        "coverage": evaluated / len(rows),
        "accuracy_when_decided": safe_div(correct, evaluated),
        "note": (
            "UNCERTAIN is treated as abstention, not a wrong operating-state claim. "
            "Coverage must be reported alongside decided-sample accuracy."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the final KaushalWatch demonstration accuracy report."
    )
    parser.add_argument("--attendance", required=True)
    parser.add_argument("--equipment", required=True)
    parser.add_argument("--operability", required=True)
    parser.add_argument("--out-dir", default="evaluation/output/final-demo")
    args = parser.parse_args()

    report = {
        "attendance": attendance_metrics(read_csv(args.attendance)),
        "equipment": equipment_metrics(read_csv(args.equipment)),
        "apparent_operability": operability_metrics(read_csv(args.operability)),
        "reporting_rules": [
            "Use only annotations from the exact demonstration dataset.",
            "Do not extrapolate these metrics to all PMKVY centres.",
            "Report UNCERTAIN operability outputs as abstentions and disclose coverage.",
            "Apparent operability is visual activity evidence, not mechanical/electrical diagnosis.",
        ],
    }

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "final_demo_report.json").write_text(json.dumps(report, indent=2))

    summary_rows = [
        ("attendance_occupancy_mae", report["attendance"]["occupancy_mae"]),
        ("attendance_alert_precision", report["attendance"]["attendance_case_detection"]["precision"]),
        ("attendance_alert_recall", report["attendance"]["attendance_case_detection"]["recall"]),
        ("attendance_alert_f1", report["attendance"]["attendance_case_detection"]["f1"]),
        ("equipment_count_mae", report["equipment"]["count_mae"]),
        ("equipment_exact_count_rate", report["equipment"]["exact_count_rate"]),
        ("operability_coverage", report["apparent_operability"]["coverage"]),
        ("operability_accuracy_when_decided", report["apparent_operability"]["accuracy_when_decided"]),
    ]
    with (out / "final_demo_summary.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        writer.writerows(summary_rows)

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
