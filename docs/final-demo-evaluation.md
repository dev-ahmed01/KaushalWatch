# Final Demonstration Evaluation

The PS requires a false-positive / false-negative assessment on the demonstration dataset. This is a **build deliverable**, not a slide-only claim.

## Required annotation files
Copy the three example CSVs in `evaluation/` and replace every row with ground truth from the exact final demonstration:

- `final_demo_attendance.example.csv`
- `final_demo_equipment.example.csv`
- `final_demo_operability.example.csv`

Do not edit the example files into fake "results"; create new local annotation files under `data/` or another gitignored location.

## Run
```bash
python evaluation/evaluate_final_demo.py \
  --attendance data/annotations/final-demo-attendance.csv \
  --equipment data/annotations/final-demo-equipment.csv \
  --operability data/annotations/final-demo-operability.csv \
  --out-dir evaluation/output/final-demo
```

Outputs:
- `final_demo_report.json`
- `final_demo_summary.csv`

## Metrics shown to judges
Attendance:
- occupancy MAE
- compliance-alert TP / FP / FN / TN
- precision
- recall
- F1
- false-positive rate
- false-negative rate

Infrastructure:
- equipment count MAE
- exact-count rate
- per-item count MAE

Apparent operability:
- coverage (fraction where the model made an ACTIVE/INACTIVE decision)
- accuracy when decided
- number of UNCERTAIN abstentions

Always show operability **coverage and accuracy together**. A system that calls everything UNCERTAIN must not look artificially accurate.

## Claim boundary
These numbers describe only the annotated demonstration dataset. They do not establish national PMKVY performance and must never be presented that way.
