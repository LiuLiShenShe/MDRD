import numpy as np
import pandas as pd

from mdrd.reporting.hypotheses import diagnose
from mdrd.reporting.reports import geometry_table, number


def test_missing_metrics_are_na_not_fabricated_zero():
    assert number(np.nan) == "N/A" and number(None) == "N/A"
    groups = pd.DataFrame([{"group": "GLOBAL_GLOBAL", "valid_pairs": 0}])
    text = geometry_table(groups)
    assert "N/A" in text


def test_empty_evidence_does_not_support_hypotheses():
    groups = pd.DataFrame([{"group": label, "valid_pairs": 0} for label in ["GLOBAL_GLOBAL", "LOCAL_LOCAL", "GLOBAL_LOCAL"]])
    blocks = pd.DataFrame(columns=["group", "jaccard", "angle_median"])
    tracks = pd.DataFrame(columns=["local_without_global", "global_local_shared"])
    matching = pd.DataFrame()
    audit = pd.DataFrame(columns=["segment", "registered"])
    parameters = {"high_covisibility": .25, "low_angle_deg": 3, "adequate_angle_deg": 5, "min_independent_blocks": 4}
    result = diagnose("test", None, groups, blocks, tracks, matching, audit, parameters)
    assert all(item["status"] == "INCONCLUSIVE" for item in result["hypotheses"].values())
