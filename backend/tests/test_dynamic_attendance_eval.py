from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.evaluate_dynamic_attendance import metrics, nearest_observation, read_manual_counts


def test_read_manual_counts(tmp_path):
    path = tmp_path / "manual.csv"
    path.write_text("second,true_count\n0.0,4\n1.0,5\n", encoding="utf-8")

    rows = read_manual_counts(path)

    assert rows == [
        {"second": 0.0, "true_count": 4},
        {"second": 1.0, "true_count": 5},
    ]


def test_nearest_observation_uses_timestamp_distance():
    observations = [
        SimpleNamespace(second=0.0),
        SimpleNamespace(second=0.2),
        SimpleNamespace(second=0.4),
    ]

    chosen = nearest_observation(observations, 0.31)

    assert chosen.second == 0.4


def test_metrics_reports_mae_bias_and_exact_rate():
    rows = [
        {"true_count": 5, "smoothed_count": 5},
        {"true_count": 5, "smoothed_count": 4},
        {"true_count": 4, "smoothed_count": 5},
    ]

    result = metrics(rows, "smoothed_count")

    assert result["mae"] == 0.6667
    assert result["median_abs_error"] == 1.0
    assert result["max_abs_error"] == 1
    assert result["mean_bias"] == 0.0
    assert result["exact_count_rate"] == 0.3333
