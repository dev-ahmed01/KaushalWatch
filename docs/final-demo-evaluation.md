# Final Demonstration Evaluation

The PS requires a false-positive / false-negative assessment on the demonstration dataset. This is a **build deliverable**, not a slide-only claim.

## Required annotation files

Copy the four example CSVs in `evaluation/` and replace every row with ground truth from the exact final demonstration:

- `final_demo_attendance.example.csv`
- `final_demo_equipment.example.csv`
- `final_demo_operability.example.csv`
- `final_demo_cases.example.csv`

Do not edit the example files into fake "results"; create new local annotation files under `data/annotations/` or another gitignored location.

The case annotation file is mandatory because the most important final metric is the behavior of the **persisted compliance-case decision**, not only the detector output. Include both positive and negative opportunities for every case type you demonstrate, for example attendance discrepancy, infrastructure compliance and camera integrity.

## Run

```bash
python evaluation/evaluate_final_demo.py \
  --attendance data/annotations/final-demo-attendance.csv \
  --equipment data/annotations/final-demo-equipment.csv \
  --operability data/annotations/final-demo-operability.csv \
  --cases data/annotations/final-demo-cases.csv \
  --out-dir evaluation/output/final-demo
```

Outputs:
- `final_demo_report.json`
- `final_demo_summary.csv`

## Metrics shown to judges

Attendance:
- occupancy MAE
- attendance-alert TP / FP / FN / TN
- precision
- recall
- F1
- false-positive rate
- false-negative rate

Infrastructure:
- equipment count MAE
- exact-count rate
- per-item count MAE
- count-derived precision / recall / F1 overall
- count-derived precision / recall / F1 by equipment class

The equipment precision/recall values are derived from annotated per-sample class counts: `TP = min(true_count, pred_count)`, with excess predictions counted as FP and missed units as FN. They are useful for the controlled demo, but they are **not bounding-box localization precision/recall** and must not be presented as such.

Apparent operability:
- coverage (fraction where the model made an ACTIVE/INACTIVE decision)
- accuracy when decided
- number of UNCERTAIN abstentions

Always show operability **coverage and accuracy together**. A system that calls everything UNCERTAIN must not look artificially accurate.

Compliance cases:
- overall TP / FP / FN / TN
- precision / recall / F1
- false-positive rate / false-negative rate
- the same confusion metrics broken down by case type

A case-opportunity row should represent a moment/window where the system had enough evidence to either create or not create a case. Include negative opportunities; evaluating only deliberately created discrepancies would make FP/TN impossible to measure.

## Claim boundary

These numbers describe only the annotated demonstration dataset. They do not establish national PMKVY performance and must never be presented that way.


## Dynamic-occupancy attendance clips

Do not score a clip with changing visible occupancy by assigning one constant manual count to the entire video. Create a timestamped CSV:

```csv
second,true_count
0.0,6
1.0,6
2.0,5
```

Then run:

```bash
python scripts/evaluate_dynamic_attendance.py \
  --video path/to/held-out.mp4 \
  --manual-csv data/annotations/held-out-attendance.csv \
  --out evaluation/output/held-out-attendance.json
```

The evaluator compares each manual timestamp with the nearest sampled observation and reports raw, registered and smoothed-count MAE, bias, maximum error and exact-count rate. It requires an authoritative detector and fails closed on detector failures.

This is separate from the compliance decision. Attendance compliance still compares stable camera occupancy with an external reported-attendance record; the timestamped evaluator exists only to measure count fidelity correctly when the scene occupancy itself changes.
