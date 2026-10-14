from evaluation.evaluate_final_demo import case_metrics, equipment_metrics


def test_equipment_metrics_include_count_precision_recall_by_item():
    report = equipment_metrics(
        [
            {"item_id": "training_panel", "true_count": "4", "pred_count": "3"},
            {"item_id": "training_panel", "true_count": "2", "pred_count": "3"},
            {"item_id": "drill_machine", "true_count": "1", "pred_count": "1"},
        ]
    )

    micro = report["count_detection"]["micro"]
    assert micro["tp"] == 6
    assert micro["fp"] == 1
    assert micro["fn"] == 1
    assert micro["precision"] == 6 / 7
    assert micro["recall"] == 6 / 7

    panel = report["count_detection"]["per_item"]["training_panel"]
    assert panel["tp"] == 5
    assert panel["fp"] == 1
    assert panel["fn"] == 1


def test_case_metrics_include_overall_and_per_type_confusion():
    report = case_metrics(
        [
            {"case_type": "attendance_discrepancy", "true_issue": "true", "pred_issue": "true"},
            {"case_type": "attendance_discrepancy", "true_issue": "false", "pred_issue": "false"},
            {"case_type": "infrastructure_compliance", "true_issue": "false", "pred_issue": "true"},
            {"case_type": "camera_integrity", "true_issue": "true", "pred_issue": "false"},
        ]
    )

    overall = report["overall"]
    assert overall["tp"] == 1
    assert overall["fp"] == 1
    assert overall["fn"] == 1
    assert overall["tn"] == 1
    assert overall["precision"] == 0.5
    assert overall["recall"] == 0.5
    assert overall["false_positive_rate"] == 0.5
    assert overall["false_negative_rate"] == 0.5

    attendance = report["per_case_type"]["attendance_discrepancy"]
    assert attendance["tp"] == 1
    assert attendance["tn"] == 1


def test_rates_without_denominator_are_unknown_not_perfect():
    from evaluation.evaluate_final_demo import (
        classification_metrics, positive_class_metrics, operability_metrics,
    )

    no_negatives = classification_metrics(tp=3, fp=0, fn=1, tn=0)
    assert no_negatives["negative_opportunities"] == 0
    assert no_negatives["false_positive_rate"] is None
    assert no_negatives["false_negative_rate"] == 0.25

    no_positives = classification_metrics(tp=0, fp=0, fn=0, tn=5)
    assert no_positives["recall"] is None
    assert no_positives["false_negative_rate"] is None
    assert no_positives["precision"] is None

    no_instances = positive_class_metrics(tp=0, fp=0, fn=0)
    assert no_instances["precision"] is None
    assert no_instances["recall"] is None

    abstained = operability_metrics([{
        "true_state": "APPARENTLY_ACTIVE",
        "pred_state": "UNCERTAIN",
    }])
    assert abstained["coverage"] == 0
    assert abstained["accuracy_when_decided"] is None


def test_unrecognized_truth_labels_and_negative_counts_are_not_silently_scored():
    import pytest
    from evaluation.evaluate_final_demo import attendance_metrics, case_metrics

    with pytest.raises(ValueError, match="Invalid case truth/prediction"):
        case_metrics([{
            "case_type": "camera_integrity",
            "true_issue": "unknown",
            "pred_issue": "false",
        }])

    with pytest.raises(ValueError, match="Attendance counts cannot be negative"):
        attendance_metrics([{
            "true_count": "-1", "pred_count": "0",
            "true_issue": "false", "pred_issue": "false",
        }])
