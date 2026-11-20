"""Example carrier set up.

Everything here is invented for demonstration. The carrier names, rates, fees,
zones and hub codes do not describe any real company or contract. To use the
checker on real invoices, copy this file, keep it out of version control, and
fill it with your own rate cards.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .rules import (
    DistanceSlabRule,
    PerKgRule,
    StateZoneRule,
    ZoneMatrixRule,
)


# Invoices rarely agree on header names. Each standard column lists the header
# spellings the checker will accept. Matching ignores case, spaces and symbols.
COLUMN_ALIASES: Dict[str, List[str]] = {
    "awb": ["awb", "awb no", "waybill", "waybill no", "consignment no", "docket no", "cn no", "lr number"],
    "origin_code": ["wh", "hub", "hub code", "warehouse", "origin code"],
    "destination_state": ["destination state", "dest state", "state", "consignee state"],
    "distance_km": ["distance", "distance km", "km"],
    "weight_kg": ["weight", "weight kg", "charged weight", "chargeable weight", "billed weight", "wt"],
    "billed_amount": ["amount", "total", "billed amount", "sub total", "invoice total"],
    "oda_charge": ["oda", "oda charge", "oda charges", "remote area charge"],
    "invoice_value": ["invoice value", "invoice amount", "order value"],
}

# Columns every sheet must provide, whatever the rule.
REQUIRED_COLUMNS = ["awb", "weight_kg", "billed_amount"]


@dataclass
class Courier:
    name: str
    rule: object
    fixed_fee: float = 0.0          # per shipment handling or documentation fee
    fuel_pct: float = 0.0           # fuel surcharge as a percentage of freight
    extra_required: List[str] = field(default_factory=list)


COURIERS: Dict[str, Courier] = {
    "Courier A": Courier(
        name="Courier A",
        rule=PerKgRule(rate=8.5, min_weight=12, min_freight=140),
        fixed_fee=30,
        fuel_pct=8,
    ),
    "Courier B": Courier(
        name="Courier B",
        rule=DistanceSlabRule(
            slabs=[(100, 3.5), (300, 4.75), (700, 5.8), (float("inf"), 7.2)],
            min_weight=25,
            min_freight=210,
        ),
        fixed_fee=45,
        extra_required=["distance_km"],
    ),
    "Courier C": Courier(
        name="Courier C",
        rule=StateZoneRule(
            zone_by_state={
                "Alpha State": "Z1",
                "Beta State": "Z1",
                "Gamma State": "Z2",
                "Delta State": "Z2",
                "Epsilon State": "Z3",
            },
            rate_by_zone={"Z1": 5.9, "Z2": 7.25, "Z3": 9.75},
            min_weight=18,
            min_freight=135,
        ),
        fixed_fee=28,
        extra_required=["destination_state"],
    ),
    "Courier D": Courier(
        name="Courier D",
        rule=ZoneMatrixRule(
            region_by_origin={"HUB1": "North", "HUB2": "West", "HUB3": "South"},
            region_by_state={
                "Alpha State": "North",
                "Beta State": "North",
                "Gamma State": "West",
                "Delta State": "South",
                "Epsilon State": "South",
            },
            grade_by_pair={
                ("North", "North"): "A", ("North", "West"): "B", ("North", "South"): "C",
                ("West", "North"): "B",  ("West", "West"): "A",  ("West", "South"): "B",
                ("South", "North"): "C", ("South", "West"): "B", ("South", "South"): "A",
            },
            rate_by_grade={"A": 6.8, "B": 9.4, "C": 12.6},
            min_weight=22,
            min_freight=300,
        ),
        fixed_fee=90,
        extra_required=["origin_code", "destination_state"],
    ),
}
