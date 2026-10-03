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
