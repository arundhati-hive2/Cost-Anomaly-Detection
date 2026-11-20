"""The checking engine.

Takes a raw invoice sheet, maps its headers onto standard names, asks the
courier's rule what the freight should have cost, and compares that with what
was billed. Rows that cannot be priced go to a review table with a reason.
"""

from __future__ import annotations

import re
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

from .config import COLUMN_ALIASES, REQUIRED_COLUMNS, Courier


def _key(text: object) -> str:
    """Lowercase and strip everything except letters and digits."""
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy whose columns use the standard names where a match exists.

    Original columns are kept, so nothing is lost. If two source columns match
    the same standard name, the first one wins.
    """
    lookup = {}
    for standard, spellings in COLUMN_ALIASES.items():
        for spelling in spellings:
            lookup[_key(spelling)] = standard

    out = df.copy()
    claimed = set()
    for col in df.columns:
        standard = lookup.get(_key(col))
        if standard and standard not in claimed and standard not in df.columns:
            out[standard] = df[col]
            claimed.add(standard)
        elif standard and standard in df.columns:
            claimed.add(standard)
    return out


def _status(variance_pct: pd.Series, tolerance_pct: float) -> pd.Series:
    status = pd.Series("OK", index=variance_pct.index, dtype=object)
    status[variance_pct > tolerance_pct] = "Overcharged"
    status[variance_pct < -tolerance_pct] = "Undercharged"
    status[variance_pct.isna()] = "Not priced"
    return status


def check_courier(
    raw: pd.DataFrame,
    courier: Courier,
    tolerance_pct: float = 2.0,
    target_cost_pct: Optional[float] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Check one sheet of invoices against one courier's rule.

    tolerance_pct: how far billed can drift from expected before a row is flagged.
    target_cost_pct: optional goal for freight as a percentage of invoice value.
    Returns (result, review).
    """
    df = normalise_columns(raw)

    needed = REQUIRED_COLUMNS + courier.extra_required
    missing = [c for c in needed if c not in df.columns]
    if missing:
        review = raw.copy()
        review["Reason"] = "Missing columns: " + ", ".join(missing)
        return pd.DataFrame(), review

    df = df.dropna(subset=["awb"]).copy()

    df["weight_kg"] = pd.to_numeric(df["weight_kg"], errors="coerce")
    df["billed_amount"] = pd.to_numeric(df["billed_amount"], errors="coerce")
    if "oda_charge" in df.columns:
        df["oda_charge"] = pd.to_numeric(df["oda_charge"], errors="coerce").fillna(0)
    else:
        df["oda_charge"] = 0.0

    rate, freight = courier.rule.calculate(df)
    df["applied_rate"] = rate
    df["expected_freight"] = freight
    df["fuel_surcharge"] = freight * courier.fuel_pct / 100
    df["fixed_fee"] = courier.fixed_fee
    df["expected_total"] = (
        df["expected_freight"] + df["fuel_surcharge"] + df["fixed_fee"] + df["oda_charge"]
    )

    df["variance"] = df["billed_amount"] - df["expected_total"]
    df["variance_pct"] = df["variance"] / df["expected_total"] * 100
    df["status"] = _status(df["variance_pct"], tolerance_pct)

    if "invoice_value" in df.columns and target_cost_pct is not None:
        invoice_value = pd.to_numeric(df["invoice_value"], errors="coerce")
        df["logistics_cost_pct"] = df["expected_total"] / invoice_value * 100
        df["gap_to_target_pct"] = target_cost_pct - df["logistics_cost_pct"]

    unpriced = df["expected_total"].isna() | df["billed_amount"].isna()
    reasons = pd.Series("", index=df.index, dtype=object)
    reasons[df["weight_kg"].isna()] = "Weight missing or not a number"
    reasons[(reasons == "") & df["applied_rate"].isna()] = (
        "No rate found: unknown state, hub code or distance"
    )
    reasons[(reasons == "") & df["billed_amount"].isna()] = "Billed amount missing"
    reasons[(reasons == "") & unpriced] = "Could not be priced"

    review = df.loc[unpriced].copy()
    review["Reason"] = reasons[unpriced]
    result = df.loc[~unpriced].copy()

    numeric_cols = [
        "applied_rate", "expected_freight", "fuel_surcharge", "expected_total",
        "variance", "variance_pct",
    ]
    result[numeric_cols] = result[numeric_cols].round(2)
    return result, review


def summarise(results: Dict[str, pd.DataFrame], reviews: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per courier: how many shipments, how many flagged, how much."""
    rows = []
    for name, res in results.items():
        over = res[res["status"] == "Overcharged"] if len(res) else res
        under = res[res["status"] == "Undercharged"] if len(res) else res
        rows.append(
            {
                "Courier": name,
                "Shipments checked": len(res),
                "Overcharged": len(over),
                "Undercharged": len(under),
                "Total overcharge": round(float(over["variance"].sum()), 2) if len(over) else 0.0,
                "Needs review": len(reviews.get(name, [])),
            }
        )
    return pd.DataFrame(rows)
