"""Create synthetic invoices for trying the checker.

Every number here is random and every carrier is invented. A handful of rows are
deliberately overcharged, undercharged or unpriceable so the app has something
to find. Run:  python sample_data/make_sample_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from checker.config import COURIERS  # noqa: E402

rng = np.random.default_rng(7)

STATES = ["Alpha State", "Beta State", "Gamma State", "Delta State", "Epsilon State"]
HUBS = ["HUB1", "HUB2", "HUB3"]
N = 40


def base_frame(prefix: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "awb": [f"{prefix}{100000 + i}" for i in range(N)],
            "origin_code": rng.choice(HUBS, N),
            "destination_state": rng.choice(STATES, N),
            "distance_km": rng.integers(20, 1200, N),
            "weight_kg": np.round(rng.uniform(4, 180, N), 1),
            "oda_charge": np.where(rng.random(N) < 0.2, rng.choice([60, 90, 120], N), 0),
            "invoice_value": rng.integers(8000, 90000, N),
        }
    )


def price(df: pd.DataFrame, courier_name: str) -> pd.Series:
    """Compute the fair price, then bend it for a few rows."""
    from checker.engine import check_courier

    courier = COURIERS[courier_name]
    probe = df.copy()
    probe["billed_amount"] = 0.0  # the checker needs the column, the value is ignored
    result, _ = check_courier(probe, courier)
    expected = result.set_index("awb")["expected_total"].reindex(df["awb"]).to_numpy()
    billed = expected * rng.uniform(0.995, 1.01, len(df))  # normal rounding noise
    idx = rng.choice(len(df), 6, replace=False)
    billed[idx[:3]] *= rng.uniform(1.12, 1.35, 3)  # overcharged
    billed[idx[3:5]] *= rng.uniform(0.70, 0.88, 2)  # undercharged
    return pd.Series(np.round(billed, 2))


def main() -> None:
    sheets = {}

    a = base_frame("CA")
    a["billed_amount"] = price(a, "Courier A")
    sheets["Courier A"] = a.rename(
        columns={
            "awb": "AWB No",
            "origin_code": "WH",
            "destination_state": "Destination State",
            "distance_km": "Distance",
            "weight_kg": "Charged Weight",
            "oda_charge": "ODA Charges",
            "billed_amount": "Amount",
            "invoice_value": "Invoice Value",
        }
    )

    b = base_frame("CB")
    b["billed_amount"] = price(b, "Courier B")
    sheets["Courier B"] = b.rename(
        columns={
            "awb": "Waybill",
            "origin_code": "Hub",
            "destination_state": "State",
            "distance_km": "Distance KM",
            "weight_kg": "Weight",
            "oda_charge": "ODA",
            "billed_amount": "Total",
            "invoice_value": "Order Value",
        }
    )
    sheets["Courier B"].loc[3, "Distance KM"] = np.nan  # cannot be priced

    c = base_frame("CC")
    c["billed_amount"] = price(c, "Courier C")
    c.loc[5, "destination_state"] = "Unknown State"  # cannot be priced
    sheets["Courier C"] = c.rename(
        columns={
            "awb": "Consignment No",
            "origin_code": "Warehouse",
            "destination_state": "Dest State",
            "distance_km": "KM",
            "weight_kg": "Wt",
            "oda_charge": "Remote Area Charge",
            "billed_amount": "Billed Amount",
            "invoice_value": "Invoice Amount",
        }
    )

    d = base_frame("CD")
    d["billed_amount"] = price(d, "Courier D")
    d.loc[8, "origin_code"] = "HUB9"  # unknown hub
    sheets["Courier D"] = d.rename(
        columns={
            "awb": "Docket No",
            "origin_code": "Hub Code",
            "destination_state": "Consignee State",
            "weight_kg": "Chargeable Weight",
            "oda_charge": "ODA Charge",
            "billed_amount": "Sub Total",
            "invoice_value": "Invoice Value",
        }
    )

    out = ROOT / "sample_data" / "sample_invoices.xlsx"
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name, index=False)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
