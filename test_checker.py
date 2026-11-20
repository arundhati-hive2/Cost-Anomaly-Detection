import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from checker import COURIERS, check_courier, normalise_columns  # noqa: E402


def frame(**cols):
    base = {"AWB No": ["X1"], "Weight": [20.0], "Amount": [0.0]}
    base.update(cols)
    return pd.DataFrame(base)


def test_header_aliases_are_mapped():
    df = normalise_columns(frame())
    assert {"awb", "weight_kg", "billed_amount"} <= set(df.columns)


def test_per_kg_rule_matches_hand_calculation():
    c = COURIERS["Courier A"]  # 8.5 per kg, floor 12 kg, min 140, fuel 8%, fee 30
    expected_freight = 20 * 8.5
    expected_total = expected_freight * 1.08 + 30
    res, rev = check_courier(frame(Amount=[expected_total]), c)
    assert rev.empty
    assert abs(res.loc[0, "expected_total"] - round(expected_total, 2)) < 0.01
    assert res.loc[0, "status"] == "OK"


def test_minimum_weight_and_minimum_freight_apply():
    c = COURIERS["Courier A"]
    res, _ = check_courier(frame(Weight=[1.0], Amount=[500.0]), c)
    # 1 kg is lifted to 12 kg (102.0), then to the 140 minimum freight
    assert res.loc[0, "expected_freight"] == 140.0


def test_overcharge_is_flagged():
    c = COURIERS["Courier A"]
    res, _ = check_courier(frame(Amount=[999.0]), c)
    assert res.loc[0, "status"] == "Overcharged"
    assert res.loc[0, "variance"] > 0


def test_undercharge_is_flagged():
    c = COURIERS["Courier A"]
    res, _ = check_courier(frame(Amount=[10.0]), c)
    assert res.loc[0, "status"] == "Undercharged"


def test_distance_slab_picks_the_right_band():
    c = COURIERS["Courier B"]
    df = frame(Distance=[250], Amount=[0.0], Weight=[100.0])
    res, _ = check_courier(df, c)
    assert res.loc[0, "applied_rate"] == 4.75


def test_unknown_state_goes_to_review_not_guessed():
    c = COURIERS["Courier C"]
    df = frame(State=["Nowhere"], Amount=[300.0])
    res, rev = check_courier(df, c)
    assert res.empty and len(rev) == 1
    assert "No rate found" in rev.iloc[0]["Reason"]


def test_missing_columns_are_reported():
    c = COURIERS["Courier D"]
    res, rev = check_courier(frame(), c)  # no hub or state columns
    assert res.empty
    assert "origin_code" in rev.iloc[0]["Reason"]


def test_zone_matrix_rule():
    c = COURIERS["Courier D"]
    df = frame(Hub=["HUB1"], State=["Alpha State"], Weight=[50.0], Amount=[0.0])
    res, _ = check_courier(df, c)
    assert res.loc[0, "applied_rate"] == 6.8  # North to North is grade A


def test_blank_weight_is_sent_to_review():
    c = COURIERS["Courier A"]
    res, rev = check_courier(frame(Weight=[np.nan], Amount=[100.0]), c)
    assert res.empty and len(rev) == 1
