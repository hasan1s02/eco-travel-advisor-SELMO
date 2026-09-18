"""Adapters for the external services used by the Eco-Travel Advisor.

Design rule for every client in this module: **never let an upstream failure
reach the traveller as an error**. Each adapter returns a result object that
carries both the payload and a provenance marker, and falls back to the
curated offline dataset when the live service is unavailable, unauthorised,
slow or over quota. The dialogue layer reads the provenance marker and tells
the user, in plain language, where the numbers came from.

Implements the section 4 requirement that "each action must include
error-handling for failed API responses and fallback messaging".
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable

import requests

from .config import CACHE_TTL_SECONDS, DATA_DIR, HTTP_TIMEOUT_SECONDS, SETTINGS
from .geo import Place, route_distance_km

logger = logging.getLogger(__name__)


DATA_PROVENANCE_NOTICE = (
    "These figures come from the offline demonstration dataset bundled with this "
    "prototype, not from a live service. Treat them as illustrative."
)


# ---------------------------------------------------------------------------
# Small TTL cache
# ---------------------------------------------------------------------------
class TTLCache:
    """Thread-safe time-boxed memo, used to stay inside free-tier quotas."""

    def __init__(self, ttl: int = CACHE_TTL_SECONDS, maxsize: int = 512) -> None:
        self._ttl = ttl
        self._maxsize = maxsize
        self._store: dict[Any, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get_or_set(self, key: Any, producer: Callable[[], Any]) -> Any:
        now = time.monotonic()
        with self._lock:
            hit = self._store.get(key)
            if hit and now - hit[0] < self._ttl:
                return hit[1]
        value = producer()
        with self._lock:
            if len(self._store) >= self._maxsize:
                self._store.clear()
            self._store[key] = (now, value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


_carbon_cache = TTLCache()
_hotel_cache = TTLCache(ttl=60 * 30)
_amadeus_token_cache: dict[str, Any] = {}
_token_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Offline datasets
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def transport_reference() -> dict[str, Any]:
    with open(DATA_DIR / "transport_factors.json", encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def hotel_reference() -> dict[str, Any]:
    with open(DATA_DIR / "eco_hotels.json", encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def experience_reference() -> dict[str, Any]:
    with open(DATA_DIR / "experiences.json", encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def offset_reference() -> dict[str, Any]:
    with open(DATA_DIR / "carbon_offsets.json", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Result envelope
# ---------------------------------------------------------------------------
@dataclass
class SourcedResult:
    """Payload plus where it came from and what went wrong on the way."""

    data: Any
    source: str  # climatiq | amadeus | offline_dataset
    degraded: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def is_live(self) -> bool:
        return self.source not in {"offline_dataset"}


# ===========================================================================
# Climatiq - transport carbon estimates
# ===========================================================================
def estimate_transport_emissions(
    mode_key: str,
    distance_km: float,
    passengers: int = 1,
) -> SourcedResult:
    """kg CO2e for one traveller covering ``distance_km`` by ``mode_key``.

    Tries Climatiq first. On any failure, applies the bundled DESNZ/DEFRA
    conversion factor instead and marks the result degraded.
    """
    factors = transport_reference()["factors"]
    if mode_key not in factors:
        raise KeyError(f"unknown transport mode {mode_key!r}")

    factor = factors[mode_key]
    cache_key = ("climatiq", mode_key, round(distance_km, 1), passengers)

    def _compute() -> SourcedResult:
        if SETTINGS.climatiq_enabled and factor["climatiq_activity_id"]:
            try:
                return _climatiq_estimate(factor, distance_km, passengers)
            except Exception as exc:
                logger.warning("Climatiq estimate failed for %s (%s); using local factor", mode_key, exc)
                return _local_estimate(
                    factor,
                    distance_km,
                    passengers,
                    notes=[f"Climatiq unavailable ({type(exc).__name__}); used the published conversion factor instead."],
                )
        return _local_estimate(factor, distance_km, passengers)

    return _carbon_cache.get_or_set(cache_key, _compute)


def _climatiq_estimate(factor: dict[str, Any], distance_km: float, passengers: int) -> SourcedResult:
    response = requests.post(
        "https://api.climatiq.io/data/v1/estimate",
        headers={
            "Authorization": f"Bearer {SETTINGS.climatiq_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "emission_factor": {
                "activity_id": factor["climatiq_activity_id"],
                "data_version": SETTINGS.climatiq_data_version,
            },
            "parameters": {
                "distance": round(distance_km, 2),
                "distance_unit": "km",
                "passengers": max(int(passengers), 1),
            },
        },
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    body = response.json()

    co2e = float(body["co2e"])
    if str(body.get("co2e_unit", "kg")).lower() in {"g", "gram", "grams"}:
        co2e /= 1000.0

    ef = body.get("emission_factor", {}) or {}
    return SourcedResult(
        data={
            "kg_co2e_total": round(co2e, 2),
            "kg_co2e_per_traveller": round(co2e / max(int(passengers), 1), 2),
            "distance_km": round(distance_km, 1),
            "factor_name": ef.get("name") or factor["label"],
            "factor_source": ef.get("source") or "Climatiq",
            "factor_year": ef.get("year"),
            "factor_region": ef.get("region"),
        },
        source="climatiq",
    )


def _local_estimate(
    factor: dict[str, Any],
    distance_km: float,
    passengers: int,
    notes: list[str] | None = None,
) -> SourcedResult:
    meta = transport_reference()["_meta"]
    per_traveller = factor["kg_per_pkm"] * distance_km
    return SourcedResult(
        data={
            "kg_co2e_total": round(per_traveller * max(int(passengers), 1), 2),
            "kg_co2e_per_traveller": round(per_traveller, 2),
            "distance_km": round(distance_km, 1),
            "factor_name": factor["label"],
            "factor_source": meta["primary_source"],
            "factor_year": 2023,
            "factor_region": "UK/EU average",
        },
        source="offline_dataset",
        degraded=True,
        notes=notes or [],
    )


def available_modes(distance_km: float) -> list[str]:
    """Modes that make physical sense over this distance.

    Prevents the assistant from proposing a bicycle for Berlin to Lisbon,
    which would be the kind of context failure the brief's UX criteria
    penalise.
    """
    rules = transport_reference()["mode_availability_rules"]
    modes = []
    for key in transport_reference()["factors"]:
        rule = rules.get(key, {})
        if distance_km < rule.get("min_km", 0):
            continue
        if distance_km > rule.get("max_km", float("inf")):
            continue
        modes.append(key)
    return modes


def network_for_mode(mode_key: str) -> str:
    if mode_key.startswith("flight"):
        return "air"
    if mode_key.startswith("rail"):
        return "rail"
    if mode_key.startswith("ferry"):
        return "ferry"
    if mode_key in {"walking", "cycling"}:
        return "active"
    return "road"


def journey_distance(origin: Place, destination: Place, mode_key: str) -> float:
    return route_distance_km(origin, destination, network_for_mode(mode_key))


# ===========================================================================
# Amadeus - accommodation
# ===========================================================================
def _amadeus_token() -> str:
    """Client-credentials token, refreshed a minute before it expires."""
    with _token_lock:
        cached = _amadeus_token_cache.get("token")
        if cached and _amadeus_token_cache.get("expires_at", 0) > time.time() + 60:
            return cached

    response = requests.post(
        f"{SETTINGS.amadeus_base_url}/v1/security/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": SETTINGS.amadeus_client_id,
            "client_secret": SETTINGS.amadeus_client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    body = response.json()

    with _token_lock:
        _amadeus_token_cache["token"] = body["access_token"]
        _amadeus_token_cache["expires_at"] = time.time() + int(body.get("expires_in", 1799))
    return body["access_token"]


def fetch_accommodation(
    destination: Place,
    check_in: str,
    check_out: str,
    adults: int = 1,
    radius_km: int = 8,
) -> SourcedResult:
    """Accommodation candidates for the destination.

    The Amadeus sandbox exposes availability and price but, as the brief
    notes, no eco-certification field. Live results are therefore *enriched*
    with the certification attributes from the offline dataset where the names
    match, and left explicitly unknown where they do not — which is the honest
    behaviour, and is what the greenwashing discussion in the report turns on.
    """
    cache_key = ("amadeus", destination.name.lower(), check_in, check_out, adults)

    def _compute() -> SourcedResult:
        if SETTINGS.amadeus_enabled:
            try:
                return _amadeus_hotels(destination, check_in, check_out, adults, radius_km)
            except Exception as exc:
                logger.warning("Amadeus hotel lookup failed for %s (%s); using offline dataset", destination.name, exc)
                return _offline_hotels(
                    destination,
                    notes=[f"Live availability unavailable ({type(exc).__name__}); showing the curated demonstration set."],
                )
        return _offline_hotels(destination)

    return _hotel_cache.get_or_set(cache_key, _compute)


def _amadeus_hotels(
    destination: Place, check_in: str, check_out: str, adults: int, radius_km: int
) -> SourcedResult:
    token = _amadeus_token()
    headers = {"Authorization": f"Bearer {token}"}

    locations = requests.get(
        f"{SETTINGS.amadeus_base_url}/v1/reference-data/locations/hotels/by-geocode",
        headers=headers,
        params={
            "latitude": round(destination.lat, 4),
            "longitude": round(destination.lon, 4),
            "radius": radius_km,
            "radiusUnit": "KM",
            "hotelSource": "ALL",
        },
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    locations.raise_for_status()
    hotel_ids = [h["hotelId"] for h in (locations.json().get("data") or [])][:12]
    if not hotel_ids:
        raise LookupError(f"no Amadeus hotels within {radius_km} km of {destination.name}")

    offers = requests.get(
        f"{SETTINGS.amadeus_base_url}/v3/shopping/hotel-offers",
        headers=headers,
        params={
            "hotelIds": ",".join(hotel_ids),
            "adults": max(int(adults), 1),
            "checkInDate": check_in,
            "checkOutDate": check_out,
            "currency": "EUR",
            "bestRateOnly": "true",
        },
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    offers.raise_for_status()

    enrichment = {
        h["name"].lower(): h
        for h in hotel_reference()["destinations"].get(_destination_key(destination), [])
    }

    results = []
    for item in (offers.json().get("data") or [])[:8]:
        hotel = item.get("hotel", {})
        offer = (item.get("offers") or [{}])[0]
        price = offer.get("price", {}).get("total")
        known = enrichment.get(str(hotel.get("name", "")).lower())
        results.append(
            {
                "id": hotel.get("hotelId"),
                "name": hotel.get("name", "Unnamed property"),
                "price_eur": float(price) if price else None,
                "district": hotel.get("cityCode"),
                # Amadeus does not publish certification status. Saying
                # "unknown" is required: inferring one would be greenwashing.
                "cert": known["cert"] if known else None,
                "cert_tier": known["cert_tier"] if known else None,
                "cert_status": "verified" if known else "unknown",
                "energy": known["energy"] if known else None,
                "single_use_plastic_free": known["single_use_plastic_free"] if known else None,
                "transit_min": known["transit_min"] if known else None,
                "local_sourcing": known["local_sourcing"] if known else None,
                "summary": known["summary"] if known else "Live availability; sustainability credentials not published by the supplier.",
            }
        )

    if not results:
        raise LookupError("Amadeus returned no bookable offers")

    return SourcedResult(
        data=results,
        source="amadeus",
        notes=["Certification status is unavailable for properties outside our verified list and is shown as unknown."],
    )


def _offline_hotels(destination: Place, notes: list[str] | None = None) -> SourcedResult:
    key = _destination_key(destination)
    properties = hotel_reference()["destinations"].get(key)

    if not properties:
        return SourcedResult(
            data=[],
            source="offline_dataset",
            degraded=True,
            notes=(notes or [])
            + [f"The demonstration dataset does not cover {destination.name} yet."],
        )

    enriched = [dict(p, cert_status="verified" if p.get("cert") else "none_claimed") for p in properties]
    return SourcedResult(
        data=enriched,
        source="offline_dataset",
        degraded=True,
        notes=(notes or []) + [DATA_PROVENANCE_NOTICE],
    )


def _destination_key(destination: Place) -> str:
    return str(destination.name).strip().lower()


# ===========================================================================
# Experiences and offsets - offline only by design
# ===========================================================================
def fetch_experiences(destination: Place, sustainability_level: str) -> SourcedResult:
    catalogue = experience_reference()["destinations"].get(_destination_key(destination), [])
    if not catalogue:
        catalogue = experience_reference()["generic"]
        note = (
            f"No curated experiences for {destination.name} yet, so these are general "
            "low-impact suggestions rather than local listings."
        )
    else:
        note = DATA_PROVENANCE_NOTICE

    if sustainability_level == "strict":
        catalogue = [e for e in catalogue if e["impact"] in {"very_low", "low"}]

    return SourcedResult(data=catalogue, source="offline_dataset", degraded=True, notes=[note])


def fetch_offsets(residual_kg: float) -> SourcedResult:
    providers = offset_reference()["providers"]
    tonnes = max(residual_kg, 0) / 1000.0
    priced = [
        dict(p, estimated_cost_eur=round(p["eur_per_tonne"] * tonnes, 2))
        for p in providers
    ]
    return SourcedResult(
        data=priced,
        source="offline_dataset",
        degraded=True,
        notes=[offset_reference()["_meta"]["integrity_warning"]],
    )


def reset_caches() -> None:
    """Used by the test suite between cases."""
    _carbon_cache.clear()
    _hotel_cache.clear()
    with _token_lock:
        _amadeus_token_cache.clear()
