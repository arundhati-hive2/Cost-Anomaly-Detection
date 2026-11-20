"""Freight rules.

Each rule answers one question: given a table of shipments, what should the
freight have cost? A rule returns two Series, the rate that was applied and the
expected freight. Anything a rule cannot price (unknown zone, missing weight)
comes back as NaN so the engine can send that row to a review sheet instead of
guessing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


@dataclass
class WeightFloor:
    """Common billing terms: a minimum billable weight and a minimum freight."""

    min_weight: float = 0.0
    min_freight: float = 0.0

    def billed_weight(self, weight: pd.Series) -> pd.Series:
        return pd.to_numeric(weight, errors="coerce").clip(lower=self.min_weight)

    def apply_minimum(self, freight: pd.Series) -> pd.Series:
        return freight.clip(lower=self.min_freight)


@dataclass
class PerKgRule(WeightFloor):
    """One flat rate per kilogram."""

    rate: float = 0.0

    def calculate(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        rate = pd.Series(self.rate, index=df.index, dtype=float)
        freight = self.billed_weight(df["weight_kg"]) * rate
        return rate, self.apply_minimum(freight)


@dataclass
class DistanceSlabRule(WeightFloor):
    """Rate depends on the distance band. Slabs are (upper_km, rate) pairs."""

    slabs: List[Tuple[float, float]] = field(default_factory=list)

    def rate_for(self, km: float) -> float:
        if pd.isna(km):
            return np.nan
        for upper, rate in self.slabs:
            if km <= upper:
                return rate
        return np.nan

    def calculate(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        rate = pd.to_numeric(df["distance_km"], errors="coerce").apply(self.rate_for)
        freight = self.billed_weight(df["weight_kg"]) * rate
        return rate, self.apply_minimum(freight)


@dataclass
class StateZoneRule(WeightFloor):
    """Destination state maps to a zone, and each zone has a rate."""

    zone_by_state: Dict[str, str] = field(default_factory=dict)
    rate_by_zone: Dict[str, float] = field(default_factory=dict)

    def calculate(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        states = df["destination_state"].astype(str).str.strip().str.upper()
        zone_map = {k.upper(): v for k, v in self.zone_by_state.items()}
        rate = states.map(zone_map).map(self.rate_by_zone)
        freight = self.billed_weight(df["weight_kg"]) * rate
        return rate, self.apply_minimum(freight)


@dataclass
class ZoneMatrixRule(WeightFloor):
    """Origin code and destination state combine into a letter grade.

    This is the shape many national carriers use: the origin hub sits in one
    region, the destination state in another, and a small matrix turns that
    pair into a rate band.
    """

    region_by_origin: Dict[str, str] = field(default_factory=dict)
    region_by_state: Dict[str, str] = field(default_factory=dict)
    grade_by_pair: Dict[Tuple[str, str], str] = field(default_factory=dict)
    rate_by_grade: Dict[str, float] = field(default_factory=dict)

    def calculate(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        origin_map = {k.upper(): v for k, v in self.region_by_origin.items()}
        state_map = {k.upper(): v for k, v in self.region_by_state.items()}

        origin_region = df["origin_code"].astype(str).str.strip().str.upper().map(origin_map)
        dest_region = df["destination_state"].astype(str).str.strip().str.upper().map(state_map)

        grades = pd.Series(
            [self.grade_by_pair.get((o, d)) for o, d in zip(origin_region, dest_region)],
            index=df.index,
        )
        rate = grades.map(self.rate_by_grade)
        freight = self.billed_weight(df["weight_kg"]) * rate
        return rate, self.apply_minimum(freight)
