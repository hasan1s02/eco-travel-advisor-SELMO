"""Weighted multi-criteria scoring for transport options and accommodation.

The brief (section 4) asks for "a weighted scoring function that combines
carbon impact, price, and user-stated preferences". This module is that
function, kept deliberately separate from the Rasa action layer so it can be
unit-tested in isolation and explained to the user on demand.

Method
------
Each option is scored on a small set of criteria. Every criterion is
min-max normalised across the candidate set to [0, 1] where 1 is always
"better", then combined as a weighted sum. Weights are chosen by the
traveller's declared ``sustainability_level``, which is what makes the same
candidate set rank differently for different people.

Why min-max rather than absolute thresholds: the traveller is choosing
between *these* options, not against a global ideal, so a 90 kg flight should
look bad next to a 12 kg train and merely mediocre next to a 140 kg drive.

Every score carries a ``rationale`` string. Showing the reasoning is a design
requirement here, not a nicety: an assistant that says "this is the greenest"
without saying why is doing the thing the sustainability literature calls
greenwashing by omission.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Iterable, Sequence

from .config import DATA_DIR

# ---------------------------------------------------------------------------
# Weight profiles
# ---------------------------------------------------------------------------
TRANSPORT_WEIGHTS: dict[str, dict[str, float]] = {
    "strict":   {"carbon": 0.65, "cost": 0.15, "time": 0.20},
    "balanced": {"carbon": 0.40, "cost": 0.30, "time": 0.30},
    "flexible": {"carbon": 0.20, "cost": 0.45, "time": 0.35},
}

ACCOMMODATION_WEIGHTS: dict[str, dict[str, float]] = {
    "strict":   {"certification": 0.35, "energy": 0.25, "transit": 0.15, "sourcing": 0.15, "cost": 0.10},
    "balanced": {"certification": 0.25, "energy": 0.20, "transit": 0.15, "sourcing": 0.10, "cost": 0.30},
    "flexible": {"certification": 0.15, "energy": 0.10, "transit": 0.15, "sourcing": 0.05, "cost": 0.55},
}

DEFAULT_LEVEL = "balanced"

# Colour bands for the result cards in the UI (section 3 of the brief).
BAND_LOW = "low"        # green
BAND_MODERATE = "moderate"  # amber
BAND_HIGH = "high"      # red


@lru_cache(maxsize=1)
def _service_levels() -> dict[str, Any]:
    with open(DATA_DIR / "transport_service_levels.json", encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def _banding() -> dict[str, float]:
    with open(DATA_DIR / "transport_factors.json", encoding="utf-8") as fh:
        return json.load(fh)["banding"]


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------
# Min-max normalisation has a known pathology: when every candidate scores
# almost the same on a criterion, the tiny spread is stretched to the full
# [0, 1] range and a meaningless difference gets full weight. A nine-hour train
# would beat a ten-hour coach on "journey time" as decisively as a one-hour
# flight beats a two-day drive, which is nonsense.
#
# The fix is relative-spread damping: if the range is small compared with the
# mean, the normalised scores are pulled back towards 0.5 (indifference)
# proportionally. A spread below SPREAD_SIGNIFICANCE of the mean is treated as
# "these are not meaningfully different on this criterion".
SPREAD_SIGNIFICANCE = 0.15


def _spread_damping(values: Sequence[float]) -> float:
    finite = [v for v in values if v is not None]
    if len(finite) < 2:
        return 1.0
    lo, hi = min(finite), max(finite)
    mean = sum(finite) / len(finite)
    if mean <= 1e-9:
        return 1.0 if (hi - lo) > 1e-9 else 0.0
    relative_spread = (hi - lo) / mean
    return min(relative_spread / SPREAD_SIGNIFICANCE, 1.0)


def _damp(scores: list[float], factor: float) -> list[float]:
    return [0.5 + (score - 0.5) * factor for score in scores]


def _normalise_lower_is_better(values: Sequence[float]) -> list[float]:
    """Map values to [0, 1] with the smallest value scoring 1.0."""
    finite = [v for v in values if v is not None]
    if not finite:
        return [0.5] * len(values)
    lo, hi = min(finite), max(finite)
    if hi - lo < 1e-9:
        return [1.0 if v is not None else 0.5 for v in values]
    raw = [1.0 - (v - lo) / (hi - lo) if v is not None else 0.5 for v in values]
    return _damp(raw, _spread_damping(values))


def _normalise_higher_is_better(values: Sequence[float]) -> list[float]:
    finite = [v for v in values if v is not None]
    if not finite:
        return [0.5] * len(values)
    lo, hi = min(finite), max(finite)
    if hi - lo < 1e-9:
        return [1.0 if v is not None else 0.5 for v in values]
    raw = [(v - lo) / (hi - lo) if v is not None else 0.5 for v in values]
    return _damp(raw, _spread_damping(values))


def resolve_weights(table: dict[str, dict[str, float]], level: str | None) -> dict[str, float]:
    return table.get(str(level or DEFAULT_LEVEL).lower(), table[DEFAULT_LEVEL])


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------
@dataclass
class TransportOption:
    mode_key: str
    label: str
    icon: str
    distance_km: float
    kg_co2e_per_traveller: float
    kg_co2e_total: float
    cost_eur_per_traveller: float
    duration_h: float
    factor_source: str
    data_source: str
    degraded: bool = False
    score: float = 0.0
    band: str = BAND_MODERATE
    rationale: str = ""
    savings_vs_worst_kg: float = 0.0
    affordable: bool = True
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode_key": self.mode_key,
            "label": self.label,
            "icon": self.icon,
            "distance_km": round(self.distance_km, 1),
            "kg_co2e_per_traveller": round(self.kg_co2e_per_traveller, 1),
            "kg_co2e_total": round(self.kg_co2e_total, 1),
            "cost_eur_per_traveller": round(self.cost_eur_per_traveller),
            "duration_h": round(self.duration_h, 1),
            "factor_source": self.factor_source,
            "data_source": self.data_source,
            "degraded": self.degraded,
            "score": round(self.score, 3),
            "band": self.band,
            "rationale": self.rationale,
            "savings_vs_worst_kg": round(self.savings_vs_worst_kg, 1),
            "affordable": self.affordable,
            "notes": self.notes,
        }


def estimate_cost_and_duration(mode_key: str, distance_km: float, travellers: int = 1) -> tuple[float, float]:
    """Indicative per-traveller fare and door-to-door journey time."""
    profile = _service_levels()["modes"].get(mode_key)
    if profile is None:
        return 0.0, 0.0

    cost = profile["eur_per_km"] * distance_km
    duration = distance_km / max(profile["avg_speed_kmh"], 1e-6) + profile["access_overhead_h"]

    # A private car's running cost is shared, not multiplied, across occupants.
    if mode_key == "car_petrol_shared" and travellers > 1:
        cost = cost / min(travellers, 4)

    credit = _service_levels()["overnight_credit"]
    if mode_key in credit["applies_to"]:
        # A sleeper replaces a hotel night, but the credit is capped so the
        # fare can never fall to zero and dominate the cost ranking.
        max_reduction = cost * credit.get("max_fare_reduction_share", 0.6)
        reduction = min(credit["assumed_night_cost_eur"] * credit["avoided_nights"], max_reduction)
        cost = max(cost - reduction, 0.0)

    return round(cost, 2), round(duration, 2)


def overnight_emissions_credit_kg(mode_key: str) -> float:
    """kg CO2e avoided by not needing a hotel night, for sleeper services."""
    credit = _service_levels()["overnight_credit"]
    if mode_key not in credit["applies_to"]:
        return 0.0
    return float(credit["assumed_night_kg_co2e"]) * int(credit["avoided_nights"])


def band_for(kg_co2e: float) -> str:
    bands = _banding()
    if kg_co2e <= bands["low_max"]:
        return BAND_LOW
    if kg_co2e <= bands["moderate_max"]:
        return BAND_MODERATE
    return BAND_HIGH


def score_transport_options(
    options: Iterable[TransportOption],
    sustainability_level: str | None,
    budget_eur: float | None = None,
) -> list[TransportOption]:
    """Rank transport options and attach a human-readable rationale."""
    items = list(options)
    if not items:
        return []

    weights = resolve_weights(TRANSPORT_WEIGHTS, sustainability_level)

    carbon_scores = _normalise_lower_is_better([o.kg_co2e_per_traveller for o in items])
    cost_scores = _normalise_lower_is_better([o.cost_eur_per_traveller for o in items])
    time_scores = _normalise_lower_is_better([o.duration_h for o in items])

    worst_carbon = max(o.kg_co2e_per_traveller for o in items)

    for option, carbon, cost, time_ in zip(items, carbon_scores, cost_scores, time_scores):
        option.score = weights["carbon"] * carbon + weights["cost"] * cost + weights["time"] * time_

        # Affordability is a hard constraint, not another weight. An option the
        # traveller cannot pay for is not a recommendation however clean it is,
        # so it drops below every affordable option regardless of score. It
        # stays visible, though — hiding it would conceal the real trade-off
        # between their budget and their emissions.
        option.affordable = not (budget_eur and option.cost_eur_per_traveller > budget_eur)
        if not option.affordable:
            option.notes.append(f"Above your stated budget of €{budget_eur:.0f}.")

        option.band = band_for(option.kg_co2e_per_traveller)
        option.savings_vs_worst_kg = worst_carbon - option.kg_co2e_per_traveller
        option.rationale = _transport_rationale(option, weights, carbon, cost, time_)

    items.sort(key=lambda o: (o.affordable, o.score), reverse=True)
    return items


def _transport_rationale(
    option: TransportOption, weights: dict[str, float], carbon: float, cost: float, time_: float
) -> str:
    dominant = max(
        (("emissions", weights["carbon"] * carbon),
         ("cost", weights["cost"] * cost),
         ("journey time", weights["time"] * time_)),
        key=lambda pair: pair[1],
    )[0]

    strengths, weaknesses = [], []
    for name, value in (("emissions", carbon), ("cost", cost), ("journey time", time_)):
        (strengths if value >= 0.66 else weaknesses if value <= 0.33 else []).append(name)

    parts = [f"Ranked mainly on {dominant}."]
    if strengths:
        parts.append(f"Strong on {_join(strengths)}.")
    if weaknesses:
        parts.append(f"Weaker on {_join(weaknesses)}.")
    return " ".join(parts)


def _join(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + f" and {items[-1]}"


# ---------------------------------------------------------------------------
# Accommodation
# ---------------------------------------------------------------------------
# Certification credibility. Tier 1 schemes are third-party audited against a
# GSTC-recognised standard; tier 2 are third-party audited; tier 3 is a
# self-declaration, which carries no independent evidence at all and is scored
# accordingly. An unknown status scores below a self-declaration is NOT correct
# -- absence of evidence is scored neutrally, absence of audit is scored low.
CERT_CREDIBILITY = {1: 1.0, 2: 0.7, 3: 0.15}
UNKNOWN_CERT_CREDIBILITY = 0.4


def score_accommodation(
    properties: Iterable[dict[str, Any]],
    sustainability_level: str | None,
    nightly_budget_eur: float | None = None,
) -> list[dict[str, Any]]:
    """Rank accommodation candidates and explain each ranking."""
    items = [dict(p) for p in properties]
    if not items:
        return []

    weights = resolve_weights(ACCOMMODATION_WEIGHTS, sustainability_level)

    cert_raw = [
        UNKNOWN_CERT_CREDIBILITY
        if p.get("cert_status") == "unknown"
        else CERT_CREDIBILITY.get(p.get("cert_tier") or 3, 0.15)
        for p in items
    ]
    energy = _normalise_higher_is_better([p.get("energy") for p in items])
    transit = _normalise_lower_is_better([p.get("transit_min") for p in items])
    sourcing = _normalise_higher_is_better([p.get("local_sourcing") for p in items])
    cost = _normalise_lower_is_better([p.get("price_eur") for p in items])

    for item, c_cert, c_energy, c_transit, c_sourcing, c_cost in zip(
        items, cert_raw, energy, transit, sourcing, cost
    ):
        item["score"] = round(
            weights["certification"] * c_cert
            + weights["energy"] * c_energy
            + weights["transit"] * c_transit
            + weights["sourcing"] * c_sourcing
            + weights["cost"] * c_cost,
            3,
        )
        item["band"] = (
            BAND_LOW if item["score"] >= 0.66 else BAND_MODERATE if item["score"] >= 0.4 else BAND_HIGH
        )

        notes: list[str] = []
        if item.get("cert_status") == "unknown":
            notes.append("Certification not published by the supplier — treated as unverified, not as absent.")
        elif not item.get("cert"):
            notes.append("No third-party certification claimed.")
        elif (item.get("cert_tier") or 3) >= 3:
            notes.append("Self-declared only; no independent audit.")

        item["affordable"] = not (nightly_budget_eur and (item.get("price_eur") or 0) > nightly_budget_eur)
        if not item["affordable"]:
            notes.append(f"Above your nightly budget of about €{nightly_budget_eur:.0f}.")

        item["rationale"] = _accommodation_rationale(item, c_cert, c_energy, c_transit, c_cost)
        item["notes"] = notes

    items.sort(key=lambda p: (p["affordable"], p["score"]), reverse=True)
    return items


def _accommodation_rationale(
    item: dict[str, Any], cert: float, energy: float, transit: float, cost: float
) -> str:
    bits = []
    if item.get("cert") and cert >= 0.7:
        bits.append(f"independently audited under {item['cert']}")
    if energy >= 0.66 and item.get("energy") is not None:
        bits.append(f"{round(item['energy'] * 100)}% renewable electricity")
    if transit >= 0.66 and item.get("transit_min") is not None:
        bits.append(f"{item['transit_min']} min walk to public transport")
    if cost >= 0.66:
        bits.append("among the cheaper options here")

    if not bits:
        return "Listed for comparison; it does not lead on any of the criteria you weighted."
    return "Ranked for " + _join(bits) + "."


def nightly_budget_from_total(total_budget_eur: float | None, nights: int, transport_cost: float) -> float | None:
    """Split the stated trip budget into a plausible nightly accommodation cap."""
    if not total_budget_eur or nights <= 0:
        return None
    remaining = total_budget_eur - transport_cost
    # Leave roughly a third of what is left for food, transit and activities.
    return max(round((remaining * 0.65) / nights, 2), 0.0) or None
