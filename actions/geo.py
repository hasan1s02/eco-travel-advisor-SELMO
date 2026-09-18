"""Location resolution and journey-distance estimation.

Two responsibilities:

1. Turn whatever the traveller typed ("lisbon", "Lisboa", "LISBON  ") or the
   coordinates their browser shared into a canonical place record.
2. Turn a pair of places into a realistic *route* distance per transport mode,
   because a straight line between two city centres is not how a train travels.

Live geocoding uses OpenCage when a key is present; otherwise the bundled
gazetteer answers, and the caller is told which happened so the assistant can
be honest about it in the UI.
"""

from __future__ import annotations

import json
import logging
import math
import re
import unicodedata
from dataclasses import dataclass, asdict
from functools import lru_cache
from typing import Any

import requests

from .config import DATA_DIR, HTTP_TIMEOUT_SECONDS, SETTINGS

logger = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371.0088

# Great-circle distance understates how far you actually travel. These are
# route-circuity multipliers: the ratio of real network distance to straight
# line distance, averaged over European city pairs.
#   rail/road figures after Ballou et al. (2002) and EEA network statistics;
#   flights add a fixed allowance for departure/arrival routing and stacking.
CIRCUITY = {
    "rail": 1.20,
    "road": 1.25,
    "ferry": 1.35,
    "air": 1.05,
    "active": 1.30,  # walking and cycling follow paths, not lines
}

_AIR_ROUTING_ALLOWANCE_KM = 40.0


@dataclass(frozen=True)
class Place:
    """A resolved location."""

    name: str
    lat: float
    lon: float
    country: str | None = None
    source: str = "gazetteer"  # gazetteer | opencage | device_gps

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class LocationNotFound(LookupError):
    """Raised when a place name cannot be resolved to coordinates."""


# ---------------------------------------------------------------------------
# Gazetteer
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _gazetteer() -> dict[str, dict[str, Any]]:
    with open(DATA_DIR / "city_gazetteer.json", encoding="utf-8") as fh:
        raw = json.load(fh)["cities"]

    index: dict[str, dict[str, Any]] = {}
    for key, record in raw.items():
        index[_normalise(key)] = record
        for alias in record.get("aliases", []):
            index[_normalise(alias)] = record
        index[_normalise(record["name"])] = record
    return index


def _normalise(text: str) -> str:
    """Casefold, strip accents and punctuation so 'Zürich' == 'zurich'."""
    decomposed = unicodedata.normalize("NFKD", str(text))
    ascii_only = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9 ]+", "", ascii_only.lower()).strip()


# Words that can only be scaffolding around a place name, never a place name
# on their own. Stripped from the start of an utterance until a real token is
# reached, so "I'm coming from Hamburg" and "to Lisbon" both resolve.
_LEADING_FILLER = {
    "i", "im", "i'm", "am", "we", "we're", "were", "are", "is", "it", "my",
    "the", "from", "to", "in", "at", "near", "around", "going", "travelling",
    "traveling", "coming", "leaving", "departing", "starting", "start", "live",
    "living", "based", "be", "will", "would", "like", "want", "currently",
    "right", "now", "over", "off",
}


def _strip_leading_prepositions(text: str) -> str:
    """Drop scaffolding words from the front until a real token appears."""
    tokens = str(text).strip().strip(" .,!?").split()
    index = 0
    while index < len(tokens) and _normalise(tokens[index]) in _LEADING_FILLER:
        index += 1
    # If every token was filler the input carried no place name at all; hand
    # back the original so the caller reports "not found" rather than "empty".
    return " ".join(tokens[index:]).strip(" .,!?") or " ".join(tokens)


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------
def geocode(query: str) -> Place:
    """Resolve a free-text place name, preferring the live geocoder."""
    cleaned = _strip_leading_prepositions(query)
    if not cleaned:
        raise LocationNotFound("empty location")

    if SETTINGS.opencage_enabled:
        try:
            return _geocode_opencage(cleaned)
        except Exception as exc:  # network, quota, malformed payload
            logger.warning("OpenCage lookup failed for %r (%s); using gazetteer", cleaned, exc)

    record = _gazetteer().get(_normalise(cleaned))
    if record is None:
        raise LocationNotFound(cleaned)
    return Place(
        name=record["name"],
        lat=float(record["lat"]),
        lon=float(record["lon"]),
        country=record.get("country"),
        source="gazetteer",
    )


def _geocode_opencage(query: str) -> Place:
    response = requests.get(
        "https://api.opencagedata.com/geocode/v1/json",
        params={
            "q": query,
            "key": SETTINGS.opencage_api_key,
            "limit": 1,
            "no_annotations": 1,
            "language": "en",
        },
        timeout=HTTP_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    results = response.json().get("results") or []
    if not results:
        raise LocationNotFound(query)

    top = results[0]
    components = top.get("components", {})
    label = (
        components.get("city")
        or components.get("town")
        or components.get("village")
        or components.get("municipality")
        or top.get("formatted", query)
    )
    return Place(
        name=label,
        lat=float(top["geometry"]["lat"]),
        lon=float(top["geometry"]["lng"]),
        country=components.get("country_code", "").upper() or None,
        source="opencage",
    )


def reverse_geocode(lat: float, lon: float) -> Place:
    """Turn browser GPS coordinates into a named place.

    Used by the "Use my location" quick reply. Falls back to the nearest
    gazetteer entry so the feature still works with no API key.
    """
    if SETTINGS.opencage_enabled:
        try:
            response = requests.get(
                "https://api.opencagedata.com/geocode/v1/json",
                params={"q": f"{lat},{lon}", "key": SETTINGS.opencage_api_key, "limit": 1, "language": "en"},
                timeout=HTTP_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            results = response.json().get("results") or []
            if results:
                components = results[0].get("components", {})
                return Place(
                    name=components.get("city") or components.get("town") or results[0].get("formatted", "your location"),
                    lat=float(lat),
                    lon=float(lon),
                    country=components.get("country_code", "").upper() or None,
                    source="device_gps",
                )
        except Exception as exc:
            logger.warning("OpenCage reverse lookup failed (%s); falling back to nearest known city", exc)

    nearest, best = None, math.inf
    for record in {id(r): r for r in _gazetteer().values()}.values():
        d = haversine_km(lat, lon, float(record["lat"]), float(record["lon"]))
        if d < best:
            nearest, best = record, d
    if nearest is None:
        raise LocationNotFound(f"{lat},{lon}")
    return Place(
        name=nearest["name"],
        lat=float(lat),
        lon=float(lon),
        country=nearest.get("country"),
        source="device_gps",
    )


# ---------------------------------------------------------------------------
# Distance
# ---------------------------------------------------------------------------
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def route_distance_km(origin: Place, destination: Place, network: str) -> float:
    """Estimated distance actually travelled over the given network."""
    straight = haversine_km(origin.lat, origin.lon, destination.lat, destination.lon)
    if network == "air":
        return round(straight * CIRCUITY["air"] + _AIR_ROUTING_ALLOWANCE_KM, 1)
    return round(straight * CIRCUITY.get(network, 1.2), 1)


def road_distance_km(origin: Place, destination: Place) -> tuple[float, str]:
    """Road distance, from OpenRouteService when available.

    Returns ``(distance_km, source)`` so the caller can report whether the
    figure is a routed distance or a circuity-adjusted estimate.
    """
    if SETTINGS.openroute_enabled:
        try:
            response = requests.post(
                "https://api.openrouteservice.org/v2/matrix/driving-car",
                headers={"Authorization": SETTINGS.openroute_api_key, "Content-Type": "application/json"},
                json={
                    "locations": [[origin.lon, origin.lat], [destination.lon, destination.lat]],
                    "metrics": ["distance"],
                    "units": "km",
                },
                timeout=HTTP_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            distance = response.json()["distances"][0][1]
            if distance:
                return round(float(distance), 1), "openrouteservice"
        except Exception as exc:
            logger.warning("OpenRouteService matrix call failed (%s); using circuity estimate", exc)

    return route_distance_km(origin, destination, "road"), "circuity_estimate"
