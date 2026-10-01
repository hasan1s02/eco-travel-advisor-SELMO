"""Rasa custom actions for the Eco-Travel Advisor.

Every action in this module follows the same three rules, which come straight
out of the assignment brief:

1. **Never fail loudly.** External calls are wrapped; a failure downgrades the
   answer and says so, it does not end the conversation.
2. **Never claim more certainty than the data supports.** Estimates are called
   estimates, demonstration data is called demonstration data, and an
   unverified certification is called unverified rather than absent.
3. **Always leave a route to a human.** Any action that cannot complete offers
   escalation rather than looping.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from rasa_sdk import Action, FormValidationAction, Tracker
from rasa_sdk.events import (
    ActiveLoop,
    AllSlotsReset,
    EventType,
    FollowupAction,
    SlotSet,
)
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from .api_clients import (
    available_modes,
    estimate_transport_emissions,
    fetch_accommodation,
    fetch_experiences,
    fetch_offsets,
    journey_distance,
    offset_reference,
    transport_reference,
)
from .config import describe_mode
from .date_utils import DateParseError, format_date, nights_between, parse_travel_date
from .eco_scoring import (
    TransportOption,
    band_for,
    estimate_cost_and_duration,
    nightly_budget_from_total,
    overnight_emissions_credit_kg,
    resolve_weights,
    score_accommodation,
    score_transport_options,
    TRANSPORT_WEIGHTS,
)
from .geo import LocationNotFound, Place, geocode, reverse_geocode
from . import handover as handover_mod

logger = logging.getLogger(__name__)

MAX_CLARIFICATION_ATTEMPTS = 2

SUSTAINABILITY_SYNONYMS = {
    "strict": "strict", "strictest": "strict", "green": "strict", "greenest": "strict",
    "lowest emissions": "strict", "most sustainable": "strict", "eco": "strict",
    "balanced": "balanced", "moderate": "balanced", "middle ground": "balanced",
    "sensible": "balanced", "trade off": "balanced", "medium": "balanced",
    "flexible": "flexible", "relaxed": "flexible", "cheapest": "flexible",
    "cost first": "flexible", "whatever is cheapest": "flexible", "cheap": "flexible",
}

WORD_NUMBERS = {
    "just me": 1, "me": 1, "myself": 1, "alone": 1, "solo": 1, "one": 1,
    "two": 2, "a couple": 2, "couple": 2, "pair": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


# ===========================================================================
# Helpers
# ===========================================================================
def _place_from_slot(tracker: Tracker, coords_slot: str, name_slot: str) -> Place | None:
    """Rebuild a Place from the slots, re-geocoding only if necessary."""
    stored = tracker.get_slot(coords_slot)
    if isinstance(stored, dict) and "lat" in stored:
        return Place(**stored)
    name = tracker.get_slot(name_slot)
    if not name:
        return None
    try:
        return geocode(str(name))
    except LocationNotFound:
        return None


def _travellers(tracker: Tracker) -> int:
    try:
        return max(int(float(tracker.get_slot("travellers") or 1)), 1)
    except (TypeError, ValueError):
        return 1


def _trip_dates(tracker: Tracker) -> tuple[date | None, date | None]:
    out: list[date | None] = []
    for slot in ("departure_date", "return_date"):
        value = tracker.get_slot(slot)
        try:
            out.append(parse_travel_date(value) if value else None)
        except DateParseError:
            out.append(None)
    return out[0], out[1]


def _source_line(degraded: bool, extra_notes: list[str] | None = None) -> str:
    """One honest sentence about where the numbers came from.

    Notes that only restate the headline are dropped: saying "this is
    demonstration data" twice in one caption reads as boilerplate, and
    boilerplate is what people stop reading.
    """
    from .api_clients import DATA_PROVENANCE_NOTICE

    mode = describe_mode()
    if mode == "live" and not degraded:
        base = "Figures from live emission-factor and availability services."
    elif degraded or mode == "demo":
        base = "Figures from the bundled demonstration dataset — illustrative, not live."
    else:
        base = "Some figures are live and some come from the bundled dataset."

    redundant = base.startswith("Figures from the bundled")
    notes = " ".join(
        note
        for note in (extra_notes or [])
        if note and not (redundant and note == DATA_PROVENANCE_NOTICE)
    )
    return f"{base} {notes}".strip()


def _uncapitalise(text: str) -> str:
    """Lower the first letter so a rationale reads as a clause, not a sentence."""
    return text[:1].lower() + text[1:] if text else text


def _offer_human(dispatcher: CollectingDispatcher, prompt: str) -> None:
    dispatcher.utter_message(
        text=prompt,
        buttons=[
            {"title": "Talk to a human advisor", "payload": "/request_human_agent"},
            {"title": "Try again", "payload": "/plan_trip"},
        ],
    )


# ===========================================================================
# Form validation - adaptive intake
# ===========================================================================
class ValidateTripForm(FormValidationAction):
    """Validates the trip intake and adapts which questions get asked."""

    def name(self) -> str:
        return "validate_trip_form"

    async def required_slots(
        self,
        domain_slots: list[str],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> list[str]:
        """Adaptive questioning.

        ``offset_interest`` is declared in the domain so its mapping
        conditions validate, but it is only actually asked of travellers on
        the strict profile, for whom the answer changes what we show. Everyone
        else never sees the question. This is the adaptive-questioning
        requirement in section 2 of the brief.
        """
        slots = list(domain_slots)

        if tracker.get_slot("sustainability_level") != "strict" and "offset_interest" in slots:
            slots.remove("offset_interest")

        return slots

    # ---------------- individual slot validators --------------------------
    async def validate_destination(
        self, value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> dict[str, Any]:
        return self._validate_place(value, dispatcher, "destination", "destination_coords")

    async def validate_origin(
        self, value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> dict[str, Any]:
        # The traveller may have tapped "Use my location" instead of typing.
        metadata = tracker.latest_message.get("metadata") or {}
        coords = metadata.get("location") or {}
        if coords.get("latitude") is not None and coords.get("longitude") is not None:
            try:
                place = reverse_geocode(float(coords["latitude"]), float(coords["longitude"]))
                dispatcher.utter_message(text=f"Thanks — I've got you near {place.name}.")
                return {"origin": place.name, "origin_coords": place.as_dict()}
            except Exception as exc:
                logger.warning("Reverse geocode failed (%s); asking for a typed origin", exc)
                dispatcher.utter_message(
                    text="I couldn't turn that location into a city. Could you type where you're starting from?"
                )
                return {"origin": None}

        result = self._validate_place(value, dispatcher, "origin", "origin_coords")

        if result.get("origin") and result["origin"] == tracker.get_slot("destination"):
            dispatcher.utter_message(
                text="That's the same as your destination. Where are you actually setting off from?"
            )
            return {"origin": None}
        return result

    def _validate_place(
        self, value: Any, dispatcher: CollectingDispatcher, slot: str, coords_slot: str
    ) -> dict[str, Any]:
        if not value:
            return {slot: None}
        try:
            place = geocode(str(value))
        except LocationNotFound:
            dispatcher.utter_message(
                text=(
                    f"I couldn't find \"{value}\". I cover European cities — try the city name on its own, "
                    "for example \"Lisbon\" or \"Ljubljana\"."
                ),
                buttons=[
                    {"title": "Lisbon", "payload": '/inform{{"city": "Lisbon"}}'},
                    {"title": "Copenhagen", "payload": '/inform{{"city": "Copenhagen"}}'},
                    {"title": "Talk to a human", "payload": "/request_human_agent"},
                ],
            )
            return {slot: None}
        except Exception as exc:
            logger.exception("Geocoding error: %s", exc)
            dispatcher.utter_message(text="My location lookup is having trouble. Could you try that once more?")
            return {slot: None}

        return {slot: place.name, coords_slot: place.as_dict()}

    async def validate_departure_date(
        self, value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> dict[str, Any]:
        try:
            parsed = parse_travel_date(value)
        except DateParseError:
            dispatcher.utter_message(
                text="I couldn't read that as a date. Try something like \"12 May 2027\", \"next Friday\" or \"in three weeks\"."
            )
            return {"departure_date": None}

        if parsed < date.today():
            dispatcher.utter_message(text=f"{format_date(parsed)} has already passed. When would you like to leave?")
            return {"departure_date": None}

        return {"departure_date": parsed.isoformat()}

    async def validate_return_date(
        self, value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> dict[str, Any]:
        try:
            parsed = parse_travel_date(value)
        except DateParseError:
            dispatcher.utter_message(text="I couldn't read that one either. A date like \"19 May 2027\" works well.")
            return {"return_date": None}

        departure_raw = tracker.get_slot("departure_date")
        if departure_raw:
            try:
                departure = parse_travel_date(departure_raw)
            except DateParseError:
                departure = None
            if departure and parsed < departure:
                dispatcher.utter_message(
                    text=f"That's before you leave on {format_date(departure)}. When are you coming back?"
                )
                return {"return_date": None}
            if departure and nights_between(departure, parsed) > 90:
                dispatcher.utter_message(
                    text=(
                        "That's a trip of over three months — I'm built for stays up to about 90 nights. "
                        "A human advisor would serve you better for something that long."
                    ),
                    buttons=[{"title": "Talk to a human advisor", "payload": "/request_human_agent"}],
                )
                return {"return_date": None}

        return {"return_date": parsed.isoformat()}

    async def validate_travellers(
        self, value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> dict[str, Any]:
        parsed = self._to_number(value, WORD_NUMBERS)
        if parsed is None or parsed < 1:
            dispatcher.utter_message(text="How many people are travelling in total? A number is fine.")
            return {"travellers": None}
        if parsed > 12:
            dispatcher.utter_message(
                text="Groups over twelve need a person to handle them properly — I'll pass you across.",
                buttons=[{"title": "Talk to a human advisor", "payload": "/request_human_agent"}],
            )
            return {"travellers": None}
        return {"travellers": float(int(parsed))}

    async def validate_budget(
        self, value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> dict[str, Any]:
        parsed = self._to_number(value, {})
        if parsed is None or parsed <= 0:
            dispatcher.utter_message(
                text="Roughly how much per person, in euros? A ballpark figure is enough — \"about 500\" works."
            )
            return {"budget": None}
        if parsed < 40:
            dispatcher.utter_message(
                text=f"€{parsed:.0f} per person is below what almost any trip costs. Shall I work with that anyway?"
            )
        return {"budget": float(parsed)}

    async def validate_sustainability_level(
        self, value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> dict[str, Any]:
        if not value:
            return {"sustainability_level": None}
        text = str(value).strip().lower()
        for key, canonical in SUSTAINABILITY_SYNONYMS.items():
            if key in text:
                return {"sustainability_level": canonical}
        dispatcher.utter_message(
            text="Pick whichever is closest — I'll use it to weight the ranking.",
            buttons=[
                {"title": "Strict", "payload": '/inform{{"sustainability_level": "strict"}}'},
                {"title": "Balanced", "payload": '/inform{{"sustainability_level": "balanced"}}'},
                {"title": "Flexible", "payload": '/inform{{"sustainability_level": "flexible"}}'},
            ],
        )
        return {"sustainability_level": None}

    @staticmethod
    def _to_number(value: Any, words: dict[str, int]) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().lower()
        for phrase, number in words.items():
            if phrase in text:
                return float(number)
        import re

        match = re.search(r"\d+(?:[.,]\d+)?", text.replace(" ", ""))
        if not match:
            return None
        try:
            return float(match.group(0).replace(",", "."))
        except ValueError:
            return None


# ===========================================================================
# Location resolution
# ===========================================================================
class ActionResolveLocations(Action):
    """Resolve origin/destination coordinates, including shared GPS."""

    def name(self) -> str:
        return "action_resolve_locations"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict[str, Any]
    ) -> list[EventType]:
        events: list[EventType] = [SlotSet("data_source_mode", describe_mode())]

        metadata = tracker.latest_message.get("metadata") or {}
        coords = metadata.get("location") or {}
        if coords.get("latitude") is not None and coords.get("longitude") is not None:
            try:
                place = reverse_geocode(float(coords["latitude"]), float(coords["longitude"]))
                dispatcher.utter_message(
                    text=(
                        f"Using your shared location near {place.name}. "
                        "I only use it for this conversation and don't store it afterwards."
                    )
                )
                events += [SlotSet("origin", place.name), SlotSet("origin_coords", place.as_dict())]
            except Exception as exc:
                logger.warning("Could not resolve shared location: %s", exc)
                dispatcher.utter_message(
                    text="I couldn't read that location. What city are you starting from?"
                )
                return events

        origin = _place_from_slot(tracker, "origin_coords", "origin")
        destination = _place_from_slot(tracker, "destination_coords", "destination")

        for place, slot in ((origin, "origin_coords"), (destination, "destination_coords")):
            if place is not None:
                events.append(SlotSet(slot, place.as_dict()))

        if origin and destination:
            from .geo import haversine_km

            straight = haversine_km(origin.lat, origin.lon, destination.lat, destination.lon)
            events.append(SlotSet("trip_distance_km", round(straight, 1)))

        return events


# ===========================================================================
# Transport comparison - the core recommendation action
# ===========================================================================
class ActionCompareTransport(Action):
    def name(self) -> str:
        return "action_compare_transport"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict[str, Any]
    ) -> list[EventType]:
        origin = _place_from_slot(tracker, "origin_coords", "origin")
        destination = _place_from_slot(tracker, "destination_coords", "destination")

        if not origin or not destination:
            dispatcher.utter_message(
                text="I need both ends of the journey before I can compare anything. Where are you travelling from and to?",
                buttons=[{"title": "Plan a trip", "payload": "/plan_trip"}],
            )
            return []

        travellers = _travellers(tracker)
        level = tracker.get_slot("sustainability_level") or "balanced"
        budget = tracker.get_slot("budget")

        from .geo import haversine_km

        straight_km = haversine_km(origin.lat, origin.lon, destination.lat, destination.lon)
        modes = available_modes(straight_km)
        if not modes:
            _offer_human(dispatcher, "I couldn't find a sensible way to cover that distance.")
            return []

        factors = transport_reference()["factors"]
        options: list[TransportOption] = []
        degraded_any = False
        notes: list[str] = []

        for mode_key in modes:
            try:
                distance = journey_distance(origin, destination, mode_key)
                estimate = estimate_transport_emissions(mode_key, distance, travellers)
            except Exception as exc:
                logger.warning("Skipping mode %s after error: %s", mode_key, exc)
                continue

            degraded_any = degraded_any or estimate.degraded
            for note in estimate.notes:
                if note not in notes:
                    notes.append(note)

            cost, duration = estimate_cost_and_duration(mode_key, distance, travellers)

            # A sleeper service removes a hotel night, so its net footprint is
            # lower than the journey alone. Reported net, with the reason shown.
            credit_kg = overnight_emissions_credit_kg(mode_key)
            per_traveller = max(estimate.data["kg_co2e_per_traveller"] - credit_kg, 0.0)
            mode_notes = (
                [f"Net of {credit_kg:.0f} kg CO₂e for the hotel night it replaces."] if credit_kg else []
            )
            if distance > 1500 and mode_key in {"rail_highspeed", "rail_national", "rail_night", "coach"}:
                mode_notes.append("Assumes a multi-leg itinerary with connections.")

            options.append(
                TransportOption(
                    mode_key=mode_key,
                    label=factors[mode_key]["label"],
                    icon=factors[mode_key]["icon"],
                    distance_km=distance,
                    kg_co2e_per_traveller=per_traveller,
                    kg_co2e_total=per_traveller * travellers,
                    cost_eur_per_traveller=cost,
                    duration_h=duration,
                    factor_source=estimate.data["factor_source"],
                    data_source=estimate.source,
                    degraded=estimate.degraded,
                    notes=mode_notes,
                )
            )

        if not options:
            _offer_human(dispatcher, "My emissions service isn't responding and I have no fallback for that route.")
            return []

        ranked = score_transport_options(options, level, budget)
        best, worst = ranked[0], max(ranked, key=lambda o: o.kg_co2e_per_traveller)

        dispatcher.utter_message(
            text=(
                f"{origin.name} to {destination.name} is about {straight_km:.0f} km in a straight line. "
                f"Here's how the options compare for {travellers} traveller"
                f"{'s' if travellers > 1 else ''}, weighted for a **{level}** profile."
            )
        )

        dispatcher.utter_message(
            json_message={
                "type": "transport_options",
                "origin": origin.name,
                "destination": destination.name,
                "travellers": travellers,
                "sustainability_level": level,
                "weights": resolve_weights(TRANSPORT_WEIGHTS, level),
                "options": [o.as_dict() for o in ranked],
                "provenance": _source_line(degraded_any, notes),
            }
        )

        saving = worst.kg_co2e_per_traveller - best.kg_co2e_per_traveller
        summary = (
            f"**{best.label}** comes out on top: about **{best.kg_co2e_per_traveller:.0f} kg CO₂e** per person, "
            f"€{best.cost_eur_per_traveller:.0f}, roughly {best.duration_h:.0f} hours door to door. "
        )
        if saving > 1:
            summary += (
                f"That's {saving:.0f} kg less per person than {worst.label.lower()} — "
                f"{saving * travellers:.0f} kg across your group."
            )
        dispatcher.utter_message(text=summary)

        # Explicit warning card for high-emission choices (section 3: "alert
        # messages highlighting high-emission options").
        high = [o for o in ranked if o.band == "high"]
        if high:
            dispatcher.utter_message(
                json_message={
                    "type": "alert",
                    "level": "warning",
                    "title": "High-emission options in this list",
                    "body": (
                        f"{', '.join(o.label for o in high[:3])} exceed "
                        f"{transport_reference()['banding']['moderate_max']:.0f} kg CO₂e per person for this journey."
                    ),
                }
            )

        return [
            SlotSet("transport_options", [o.as_dict() for o in ranked]),
            SlotSet("trip_distance_km", round(straight_km, 1)),
            SlotSet("data_source_mode", describe_mode()),
        ]


class ActionReportCarbonForSelection(Action):
    """Answer 'what does the train specifically cost in carbon?'"""

    def name(self) -> str:
        return "action_report_carbon_for_selection"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict[str, Any]
    ) -> list[EventType]:
        options = tracker.get_slot("transport_options") or []
        selection = (tracker.get_slot("selected_transport") or "").lower()

        if not options:
            dispatcher.utter_message(text="I haven't compared any routes yet — tell me where you're going first.")
            return []

        match = next(
            (o for o in options if selection and (selection in o["mode_key"] or selection in o["label"].lower())),
            options[0],
        )
        dispatcher.utter_message(
            text=(
                f"**{match['label']}**: about {match['kg_co2e_per_traveller']:.0f} kg CO₂e per person over "
                f"{match['distance_km']:.0f} km, around €{match['cost_eur_per_traveller']:.0f} and "
                f"{match['duration_h']:.0f} hours. {match['rationale']}"
            )
        )
        return []


# ===========================================================================
# Accommodation
# ===========================================================================
class ActionRecommendHotels(Action):
    def name(self) -> str:
        return "action_recommend_hotels"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict[str, Any]
    ) -> list[EventType]:
        destination = _place_from_slot(tracker, "destination_coords", "destination")
        if not destination:
            dispatcher.utter_message(response="utter_no_trip_context")
            return []

        departure, return_date = _trip_dates(tracker)
        nights = nights_between(departure, return_date) if departure and return_date else 2
        travellers = _travellers(tracker)
        level = tracker.get_slot("sustainability_level") or "balanced"

        transport = tracker.get_slot("transport_options") or []
        transport_cost = float(transport[0]["cost_eur_per_traveller"]) if transport else 0.0
        nightly_cap = nightly_budget_from_total(tracker.get_slot("budget"), max(nights, 1), transport_cost)

        try:
            result = fetch_accommodation(
                destination,
                check_in=departure.isoformat() if departure else date.today().isoformat(),
                check_out=return_date.isoformat() if return_date else date.today().isoformat(),
                adults=travellers,
            )
        except Exception as exc:
            logger.exception("Accommodation lookup failed: %s", exc)
            _offer_human(dispatcher, "My accommodation lookup failed and I don't want to guess at it.")
            return []

        if not result.data:
            dispatcher.utter_message(
                text=(
                    f"I don't have verified accommodation for {destination.name} in this build. "
                    "I'd rather say that than invent a list."
                ),
                buttons=[
                    {"title": "Talk to a human advisor", "payload": "/request_human_agent"},
                    {"title": "Try another city", "payload": "/change_preference"},
                ],
            )
            return []

        ranked = score_accommodation(result.data, level, nightly_cap)

        header = f"Places to stay in {destination.name}"
        if nights:
            header += f" for {nights} night{'s' if nights != 1 else ''}"
        if nightly_cap:
            header += f", aiming under about €{nightly_cap:.0f} a night"
        dispatcher.utter_message(text=header + ".")

        dispatcher.utter_message(
            json_message={
                "type": "hotel_carousel",
                "destination": destination.name,
                "nights": nights,
                "nightly_budget_eur": nightly_cap,
                "sustainability_level": level,
                "hotels": ranked[:6],
                "provenance": _source_line(result.degraded, result.notes),
            }
        )

        top = ranked[0]
        line = f"**{top['name']}** ranks first — {_uncapitalise(top['rationale'])}"
        if top.get("price_eur"):
            line += f" About €{top['price_eur']:.0f} a night"
            if nights:
                line += f", so roughly €{top['price_eur'] * nights:.0f} for the stay."
            else:
                line += "."
        dispatcher.utter_message(text=line)

        unverified = [h for h in ranked[:6] if h.get("cert_status") == "unknown"]
        if unverified:
            dispatcher.utter_message(
                json_message={
                    "type": "alert",
                    "level": "info",
                    "title": "Some credentials are unverified",
                    "body": (
                        f"{len(unverified)} of these properties publish no certification through the booking API. "
                        "I've marked them unverified rather than assuming either way."
                    ),
                }
            )

        return [SlotSet("hotel_options", ranked)]


# ===========================================================================
# Experiences
# ===========================================================================
class ActionRecommendExperiences(Action):
    def name(self) -> str:
        return "action_recommend_experiences"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict[str, Any]
    ) -> list[EventType]:
        destination = _place_from_slot(tracker, "destination_coords", "destination")
        if not destination:
            dispatcher.utter_message(response="utter_no_trip_context")
            return []

        level = tracker.get_slot("sustainability_level") or "balanced"
        result = fetch_experiences(destination, level)

        if not result.data:
            dispatcher.utter_message(text=f"I don't have curated activities for {destination.name} yet.")
            return []

        dispatcher.utter_message(
            text=f"Things to do in {destination.name} that keep impact low and money local:"
        )
        dispatcher.utter_message(
            json_message={
                "type": "experience_list",
                "destination": destination.name,
                "experiences": result.data,
                "provenance": _source_line(result.degraded, result.notes),
            }
        )
        return []


# ===========================================================================
# Offsets - shown only after reductions, and with the caveats attached
# ===========================================================================
class ActionRecommendOffsets(Action):
    def name(self) -> str:
        return "action_recommend_offsets"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict[str, Any]
    ) -> list[EventType]:
        options = tracker.get_slot("transport_options") or []
        travellers = _travellers(tracker)

        if options:
            best = options[0]
            residual = float(best["kg_co2e_per_traveller"]) * travellers * 2  # return journey
            context = (
                f"Taking the {best['label'].lower()} both ways, your group's journey emissions come to "
                f"about **{residual:.0f} kg CO₂e**."
            )
        else:
            residual = 250.0 * travellers
            context = (
                "I don't have your route yet, so this uses a placeholder of 250 kg CO₂e per traveller. "
                "Plan the trip first and I'll price it against your real figure."
            )

        reduction_prompt = offset_reference()["reduction_first_prompts"][0]
        dispatcher.utter_message(
            text=(
                f"{context}\n\n"
                "Before offsets: offsetting does not undo a journey, and the evidence behind many credits is weak. "
                f"{reduction_prompt}"
            )
        )

        result = fetch_offsets(residual)
        dispatcher.utter_message(
            json_message={
                "type": "offset_list",
                "residual_kg_co2e": round(residual, 1),
                "providers": result.data,
                "provenance": _source_line(result.degraded, result.notes),
            }
        )
        return []


# ===========================================================================
# Summary
# ===========================================================================
class ActionTripSummary(Action):
    def name(self) -> str:
        return "action_trip_summary"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict[str, Any]
    ) -> list[EventType]:
        destination = tracker.get_slot("destination")
        if not destination:
            dispatcher.utter_message(response="utter_no_trip_context")
            return []

        departure, return_date = _trip_dates(tracker)
        nights = nights_between(departure, return_date) if departure and return_date else 0
        travellers = _travellers(tracker)
        transport = tracker.get_slot("transport_options") or []
        hotels = tracker.get_slot("hotel_options") or []

        best_transport = transport[0] if transport else None
        best_hotel = hotels[0] if hotels else None

        journey_kg = float(best_transport["kg_co2e_per_traveller"]) * 2 if best_transport else 0.0
        stay_kg = (nights * 12.0) if nights else 0.0  # see methodology action
        total_per_traveller = journey_kg + stay_kg

        transport_cost = float(best_transport["cost_eur_per_traveller"]) * 2 if best_transport else 0.0
        hotel_cost = (float(best_hotel.get("price_eur") or 0) * nights) if best_hotel else 0.0

        dispatcher.utter_message(
            json_message={
                "type": "trip_summary",
                "origin": tracker.get_slot("origin"),
                "destination": destination,
                "departure_date": format_date(departure) if departure else None,
                "return_date": format_date(return_date) if return_date else None,
                "nights": nights,
                "travellers": travellers,
                "sustainability_level": tracker.get_slot("sustainability_level"),
                "transport": best_transport,
                "accommodation": best_hotel,
                "footprint": {
                    "journey_kg_per_traveller": round(journey_kg, 1),
                    "stay_kg_per_traveller": round(stay_kg, 1),
                    "total_kg_per_traveller": round(total_per_traveller, 1),
                    "total_kg_group": round(total_per_traveller * travellers, 1),
                    "band": band_for(total_per_traveller),
                },
                "estimated_cost_eur_per_traveller": round(transport_cost + hotel_cost),
                "provenance": _source_line(describe_mode() != "live"),
            }
        )

        if best_transport:
            dispatcher.utter_message(
                text=(
                    f"All in, about **{total_per_traveller:.0f} kg CO₂e per traveller** "
                    f"({total_per_traveller * travellers:.0f} kg for the group): "
                    f"{journey_kg:.0f} kg travelling and {stay_kg:.0f} kg for {nights} night"
                    f"{'s' if nights != 1 else ''} of accommodation. "
                    "Ask me how I worked that out any time."
                ),
                buttons=[
                    {"title": "How did you calculate this?", "payload": "/ask_methodology"},
                    {"title": "Offset the remainder", "payload": "/ask_carbon_offset"},
                    {"title": "Talk to a human advisor", "payload": "/request_human_agent"},
                ],
            )
        else:
            dispatcher.utter_message(
                text="I've got your trip details but haven't compared routes yet.",
                buttons=[{"title": "Compare travel options", "payload": "/ask_transport_options"}],
            )
        return []


# ===========================================================================
# Transparency
# ===========================================================================
class ActionExplainMethodology(Action):
    """The anti-greenwashing action: show the working, name the limits."""

    def name(self) -> str:
        return "action_explain_methodology"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict[str, Any]
    ) -> list[EventType]:
        mode = describe_mode()
        level = tracker.get_slot("sustainability_level") or "balanced"
        weights = resolve_weights(TRANSPORT_WEIGHTS, level)
        meta = transport_reference()["_meta"]

        dispatcher.utter_message(
            text=(
                "Here's exactly how the numbers are produced.\n\n"
                "**Emissions.** Distance × a published emission factor per passenger-kilometre. "
                f"Factors come from {meta['primary_source']}"
                + (", fetched live from Climatiq where available." if mode in {"live", "hybrid"} else ", bundled offline in this build.")
                + " Straight-line distance is multiplied by a route-circuity factor (1.20 rail, 1.25 road, 1.05 air plus a 40 km routing allowance), "
                "because trains and roads don't travel in straight lines.\n\n"
                "**Ranking.** A weighted sum of three min-max normalised criteria. On your "
                f"**{level}** profile that's emissions {weights['carbon']:.0%}, cost {weights['cost']:.0%}, "
                f"journey time {weights['time']:.0%}. Options over your budget are demoted rather than hidden.\n\n"
                "**Accommodation.** Ranked on certification credibility (audited against a GSTC-recognised standard "
                "beats audited, which beats self-declared), renewable electricity share, walking distance to transit, "
                "local sourcing and price."
            )
        )
        dispatcher.utter_message(
            text=(
                "**And what these numbers are not.**\n\n"
                "They're fleet averages, not measurements of your specific journey — load factor, aircraft type and "
                "electricity mix all move the real figure. Accommodation emissions use a flat 12 kg per person per "
                "night, which is a rough European hotel average and nothing more. "
                + (
                    "Availability, prices and certifications in this build come from a bundled demonstration dataset, "
                    "so treat them as illustrative rather than bookable."
                    if mode != "live"
                    else "Certification status is only shown where a supplier actually publishes it; elsewhere I mark it unverified."
                )
                + "\n\nIf a number matters to a real decision, check it against the operator's own reporting."
            ),
            buttons=[
                {"title": "Carry on planning", "payload": "/ask_transport_options"},
                {"title": "Talk to a human advisor", "payload": "/request_human_agent"},
            ],
        )
        return []


class ActionExplainPrivacy(Action):
    def name(self) -> str:
        return "action_explain_privacy"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict[str, Any]
    ) -> list[EventType]:
        dispatcher.utter_message(
            text=(
                "**What I hold.** Only what you've told me for this trip: origin, destination, dates, group size, "
                "budget and your sustainability preference. If you shared your location, it's used to work out a "
                "starting point and is not kept afterwards.\n\n"
                "**Where it goes.** Nowhere, unless you ask for a human advisor — and then only the trip brief, the "
                "options I showed you and a transcript, with email addresses, phone numbers and ID-like numbers "
                "stripped out automatically before sending.\n\n"
                "**How long.** The conversation is held in memory for this session and expires after 60 minutes of "
                "inactivity. There's no advertising or profiling on any of it.\n\n"
                "**Your rights.** Say \"start over\" and I'll erase everything I'm holding right now."
            ),
            buttons=[
                {"title": "Erase and start over", "payload": "/restart_planning"},
                {"title": "Carry on planning", "payload": "/plan_trip"},
            ],
        )
        return []


# ===========================================================================
# Error recovery: two-stage clarification
# ===========================================================================
class ActionTwoStageClarification(Action):
    """Re-prompt once with open text, once with constrained options, then escalate.

    This action is wired as ``core_fallback_action_name`` as well as the
    handler for the ``nlu_fallback`` intent, which makes turn termination its
    responsibility. Rasa appends ``action_listen`` automatically only after the
    built-in ``action_default_fallback``; a custom fallback action that simply
    returns will be predicted again on the very next step, from the same
    unchanged state, and the conversation spins forever. Every branch below
    therefore ends the turn explicitly with ``FollowupAction("action_listen")``.
    """

    def name(self) -> str:
        return "action_two_stage_clarification"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict[str, Any]
    ) -> list[EventType]:
        stage = int(float(tracker.get_slot("clarification_stage") or 0))
        last_text = (tracker.latest_message.get("text") or "").strip()

        if stage == 0:
            dispatcher.utter_message(
                text=(
                    f"I'm not sure what you meant by \"{last_text[:80]}\"."
                    if last_text
                    else "I didn't quite catch that."
                )
                + " Could you put it another way?"
            )
            return [SlotSet("clarification_stage", 1), FollowupAction("action_listen")]

        if stage == 1:
            dispatcher.utter_message(
                text="Still not with you — let me narrow it down. Which of these is closest?",
                buttons=[
                    {"title": "Plan a trip", "payload": "/plan_trip"},
                    {"title": "Compare travel options", "payload": "/ask_transport_options"},
                    {"title": "Find places to stay", "payload": "/ask_eco_hotels"},
                    {"title": "Things to do", "payload": "/ask_cultural_experiences"},
                    {"title": "None of these — get me a human", "payload": "/request_human_agent"},
                ],
            )
            return [SlotSet("clarification_stage", 2), FollowupAction("action_listen")]

        # Stage 2+: stop asking and hand over. Looping is worse than escalating.
        #
        # The handover runs inline rather than as a FollowupAction to another
        # custom action: that action would itself be re-predicted by the same
        # fallback, reproducing the loop one level down.
        dispatcher.utter_message(
            text="I've asked twice and I'm still not following — that's my limit, not yours. Passing you to a person."
        )
        events = perform_handover(dispatcher, tracker, reason="repeated_misunderstanding")
        return events + [FollowupAction("action_listen")]


# ===========================================================================
# Human escalation
# ===========================================================================
def perform_handover(
    dispatcher: CollectingDispatcher, tracker: Tracker, reason: str
) -> list[EventType]:
    """Package the conversation, send it to the advisor desk, tell the traveller.

    Module-level rather than a method so the clarification action can escalate
    inline without chaining to another custom action, which the core fallback
    would re-predict and loop on.
    """
    slots = {key: tracker.get_slot(key) for key in tracker.slots}

    payload = handover_mod.build_payload(
        slots=slots,
        events=list(tracker.events),
        reason=reason,
        sender_id=tracker.sender_id,
        data_source_mode=describe_mode(),
    )
    delivered, channel = handover_mod.dispatch(payload)

    missing = payload["unresolved_fields"]
    brief_lines = [
        f"- {label}: {value}"
        for label, value in (
            ("Route", f"{slots.get('origin') or '—'} → {slots.get('destination') or '—'}"),
            ("Dates", f"{slots.get('departure_date') or '—'} to {slots.get('return_date') or '—'}"),
            ("Travellers", f"{int(float(slots['travellers']))}" if slots.get("travellers") else "—"),
            ("Budget", f"€{slots['budget']:.0f}" if slots.get("budget") else "—"),
            ("Priority", slots.get("sustainability_level") or "—"),
        )
    ]

    if delivered:
        dispatcher.utter_message(
            text=(
                f"Passing you to a human travel advisor. Your reference is **{payload['reference']}**.\n\n"
                "They'll receive everything we've covered, so you won't have to repeat yourself:\n"
                + "\n".join(brief_lines)
                + (f"\n\nStill open: {', '.join(missing)} — they'll pick those up with you." if missing else "")
            )
        )
    else:
        dispatcher.utter_message(
            text=(
                "I couldn't reach the advisor desk just now. Nothing is lost — here's your brief so you can "
                "send it across directly:\n" + "\n".join(brief_lines)
            )
        )

    dispatcher.utter_message(
        json_message={
            "type": "handover",
            "status": "delivered" if delivered else "failed",
            "channel": channel,
            "reference": payload["reference"],
            "reason": reason,
            "trip_brief": payload["trip_brief"],
            "advisor_notes": payload["advisor_notes"],
        }
    )

    return [
        SlotSet("handover_active", True),
        SlotSet("handover_reference", payload["reference"]),
        SlotSet("clarification_stage", 0),
    ]


class ActionHandoverToHuman(Action):
    """Escalate because the traveller asked. Reached through its own rule, which
    already ends the turn, so no explicit action_listen is needed here."""

    def name(self) -> str:
        return "action_handover_to_human"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict[str, Any]
    ) -> list[EventType]:
        reason = (
            "repeated_misunderstanding"
            if int(float(tracker.get_slot("clarification_stage") or 0)) >= MAX_CLARIFICATION_ATTEMPTS
            else "traveller_request"
        )
        return perform_handover(dispatcher, tracker, reason)


# ===========================================================================
# Reset
# ===========================================================================
class ActionResetPlanning(Action):
    def name(self) -> str:
        return "action_reset_planning"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict[str, Any]
    ) -> list[EventType]:
        dispatcher.utter_message(
            text="Everything cleared — origin, destination, dates, budget and preferences are all gone from memory.",
            buttons=[{"title": "Plan a new trip", "payload": "/plan_trip"}],
        )
        return [AllSlotsReset(), ActiveLoop(None), SlotSet("clarification_stage", 0)]
