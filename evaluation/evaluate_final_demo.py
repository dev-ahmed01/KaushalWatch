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


def positive_class_metrics(tp: int, fp: int, fn: int) -> dict:
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    f1 = safe_div(2 * precision * recall, precision + recall)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def bump_confusion(counts: dict[str, int], truth: bool, pred: bool) -> None:
    if truth and pred:
        counts["tp"] += 1
    elif not truth and pred:
        counts["fp"] += 1
    elif truth and not pred:
        counts["fn"] += 1
    else:
        counts["tn"] += 1


def attendance_metrics(rows: list[dict[str, str]]) -> dict:
    errors: list[int] = []
    counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for row in rows:
        true_count = int(row["true_count"])
        pred_count = int(row["pred_count"])
        errors.append(abs(true_count - pred_count))
        bump_confusion(
            counts,
            to_bool(row["true_issue"]),
            to_bool(row["pred_issue"]),
        )
    return {
        "samples": len(rows),
        "occupancy_mae": sum(errors) / len(errors),
        "max_count_error": max(errors),
        "attendance_case_detection": classification_metrics(**counts),
    }


def equipment_metrics(rows: list[dict[str, str]]) -> dict:
    per_item_errors: dict[str, list[int]] = defaultdict(list)
    per_item_confusion: dict[str, dict[str, int]] = defaultdict(
        lambda: {"tp": 0, "fp": 0, "fn": 0}
    )
    all_errors: list[int] = []
    exact = 0
    under = 0
    over = 0
    micro = {"tp": 0, "fp": 0, "fn": 0}

    for row in rows:
        item = row["item_id"]
        true_count = int(row["true_count"])
        pred_count = int(row["pred_count"])
        if true_count < 0 or pred_count < 0:
            raise ValueError("Equipment counts cannot be negative")

        error = abs(true_count - pred_count)
        per_item_errors[item].append(error)
        all_errors.append(error)
        if pred_count == true_count:
            exact += 1
        elif pred_count < true_count:
            under += 1
        else:
            over += 1

        # Count-derived instance metrics: a predicted unit can match at most one
        # ground-truth unit of the same class in the same annotated sample.
        tp = min(true_count, pred_count)
        fp = max(pred_count - true_count, 0)
        fn = max(true_count - pred_count, 0)
        micro["tp"] += tp
        micro["fp"] += fp
        micro["fn"] += fn
        per_item_confusion[item]["tp"] += tp
        per_item_confusion[item]["fp"] += fp
        per_item_confusion[item]["fn"] += fn

    return {
        "samples": len(rows),
        "count_mae": sum(all_errors) / len(all_errors),
        "exact_count_rate": exact / len(rows),
        "under_count_rate": under / len(rows),
        "over_count_rate": over / len(rows),
        "per_item_count_mae": {
            item: sum(errors) / len(errors)
            for item, errors in sorted(per_item_errors.items())
        },
        "count_detection": {
            "micro": positive_class_metrics(**micro),
            "per_item": {
                item: positive_class_metrics(**counts)
                for item, counts in sorted(per_item_confusion.items())
            },
            "note": (
                "Precision/recall are derived from per-sample class counts. "
                "They do not claim bounding-box localization precision/recall."
            ),
        },
    }


def case_metrics(rows: list[dict[str, str]]) -> dict:
    overall = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    per_type: dict[str, dict[str, int]] = defaultdict(
        lambda: {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    )

    for row in rows:
        case_type = row["case_type"].strip()
        if not case_type:
            raise ValueError("case_type cannot be blank")
        truth = to_bool(row["true_issue"])
        pred = to_bool(row["pred_issue"])
        bump_confusion(overall, truth, pred)
        bump_confusion(per_type[case_type], truth, pred)

    return {
        "samples": len(rows),
        "overall": classification_metrics(**overall),
        "per_case_type": {
            case_type: classification_metrics(**counts)
            for case_type, counts in sorted(per_type.items())
        },
        "note": (
            "Each row represents an independently annotated compliance-case opportunity. "
            "Use the exact final demonstration scenario, including negative opportunities."
        ),
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
    parser.add_argument(
        "--cases",
        required=True,
        help="CSV of independently annotated compliance-case opportunities",
    )
    parser.add_argument("--out-dir", default="evaluation/output/final-demo")
    args = parser.parse_args()

    report = {
        "attendance": attendance_metrics(read_csv(args.attendance)),
        "equipment": equipment_metrics(read_csv(args.equipment)),
        "apparent_operability": operability_metrics(read_csv(args.operability)),
        "compliance_cases": case_metrics(read_csv(args.cases)),
        "reporting_rules": [
            "Use only annotations from the exact demonstration dataset.",
            "Do not extrapolate these metrics to all PMKVY centres.",
            "Report UNCERTAIN operability outputs as abstentions and disclose coverage.",
            "Apparent operability is visual activity evidence, not mechanical/electrical diagnosis.",
            (
                "Equipment precision/recall in this report are count-derived class metrics, "
                "not bounding-box localization metrics."
            ),
            (
                "Compliance-case TP/FP/FN/TN must include negative case opportunities, "
                "not only moments where a discrepancy was expected."
            ),
        ],
    }

    case_overall = report["compliance_cases"]["overall"]
    equipment_micro = report["equipment"]["count_detection"]["micro"]

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "final_demo_report.json").write_text(json.dumps(report, indent=2))

    summary_rows = [
        ("attendance_occupancy_mae", report["attendance"]["occupancy_mae"]),
        (
            "attendance_alert_precision",
            report["attendance"]["attendance_case_detection"]["precision"],
        ),
        (
            "attendance_alert_recall",
            report["attendance"]["attendance_case_detection"]["recall"],
        ),
        (
            "attendance_alert_f1",
            report["attendance"]["attendance_case_detection"]["f1"],
        ),
        ("equipment_count_mae", report["equipment"]["count_mae"]),
        ("equipment_exact_count_rate", report["equipment"]["exact_count_rate"]),
        ("equipment_count_precision", equipment_micro["precision"]),
        ("equipment_count_recall", equipment_micro["recall"]),
        ("equipment_count_f1", equipment_micro["f1"]),
        ("operability_coverage", report["apparent_operability"]["coverage"]),
        (
            "operability_accuracy_when_decided",
            report["apparent_operability"]["accuracy_when_decided"],
        ),
        ("compliance_case_tp", case_overall["tp"]),
        ("compliance_case_fp", case_overall["fp"]),
        ("compliance_case_fn", case_overall["fn"]),
        ("compliance_case_tn", case_overall["tn"]),
        ("compliance_case_precision", case_overall["precision"]),
        ("compliance_case_recall", case_overall["recall"]),
        ("compliance_case_f1", case_overall["f1"]),
        ("compliance_case_fpr", case_overall["false_positive_rate"]),
        ("compliance_case_fnr", case_overall["false_negative_rate"]),
    ]
    with (out / "final_demo_summary.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        writer.writerows(summary_rows)

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
