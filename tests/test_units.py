"""Unit tests for the deterministic layer beneath the Rasa actions.

These cover the parts where a silent bug would produce a plausible-looking but
wrong number — which, for a tool whose whole purpose is to be trusted about
emissions, is the worst failure mode available to it.

Run with:  pytest tests/ -v
"""

from __future__ import annotations

import json
from datetime import date

import pytest
import responses

from actions import api_clients, eco_scoring, geo, handover
from actions.date_utils import DateParseError, format_date, nights_between, parse_travel_date

TODAY = date(2026, 9, 18)  # a Friday, matching the submission build date


# ===========================================================================
# Date parsing
# ===========================================================================
@pytest.mark.parametrize(
    ("utterance", "expected"),
    [
        ("2027-05-12", date(2027, 5, 12)),
        ("12 May 2027", date(2027, 5, 12)),
        ("May 12 2027", date(2027, 5, 12)),
        ("12/05/2027", date(2027, 5, 12)),
        ("15th of June", date(2027, 6, 15)),
        ("on the 3rd of May 2027", date(2027, 5, 3)),
        ("I want to leave on 12 May", date(2027, 5, 12)),
        ("tomorrow", date(2026, 9, 19)),
        ("in three weeks", date(2026, 10, 9)),
        ("in 10 days", date(2026, 9, 28)),
        ("next month", date(2026, 10, 18)),
        ("mid July", date(2027, 7, 15)),
    ],
)
def test_parses_the_phrasings_travellers_actually_use(utterance: str, expected: date) -> None:
    assert parse_travel_date(utterance, today=TODAY) == expected


@pytest.mark.parametrize("utterance", ["banana", "", "   ", "sometime", "31 February 2027", "45/13/2027"])
def test_rejects_rather_than_guesses(utterance: str) -> None:
    """A wrong date silently accepted is worse than a re-prompt."""
    with pytest.raises(DateParseError):
        parse_travel_date(utterance, today=TODAY)


def test_bare_month_day_rolls_forward_to_the_next_occurrence() -> None:
    """In September, '12 May' means next May, not the one that has passed."""
    assert parse_travel_date("12 May", today=TODAY).year == 2027
    assert parse_travel_date("12 December", today=TODAY).year == 2026


def test_formatting_and_night_counting() -> None:
    assert format_date(date(2027, 5, 12)) == "12 May 2027"
    assert nights_between(date(2027, 5, 12), date(2027, 5, 19)) == 7
    assert nights_between(date(2027, 5, 19), date(2027, 5, 12)) == 0  # never negative


# ===========================================================================
# Geography
# ===========================================================================
def test_geocoder_is_accent_and_case_insensitive() -> None:
    for query in ("Zurich", "zürich", "  ZURICH  "):
        assert geo.geocode(query).name == "Zurich"


def test_geocoder_strips_conversational_prefixes() -> None:
    assert geo.geocode("I'm coming from Hamburg").name == "Hamburg"
    assert geo.geocode("to Lisbon").name == "Lisbon"


def test_unknown_place_raises_rather_than_returning_a_wrong_city() -> None:
    with pytest.raises(geo.LocationNotFound):
        geo.geocode("Definitelynotacity")


def test_haversine_against_a_known_distance() -> None:
    """Berlin to Vienna is ~524 km great-circle; allow 1% for rounding."""
    berlin, vienna = geo.geocode("Berlin"), geo.geocode("Vienna")
    km = geo.haversine_km(berlin.lat, berlin.lon, vienna.lat, vienna.lon)
    assert 519 < km < 529


def test_route_distance_exceeds_straight_line_for_every_network() -> None:
    a, b = geo.geocode("Berlin"), geo.geocode("Vienna")
    straight = geo.haversine_km(a.lat, a.lon, b.lat, b.lon)
    for network in ("rail", "road", "air", "ferry", "active"):
        assert geo.route_distance_km(a, b, network) > straight


def test_reverse_geocode_falls_back_to_nearest_known_city() -> None:
    place = geo.reverse_geocode(52.52, 13.40)
    assert place.name == "Berlin"
    assert place.source == "device_gps"


# ===========================================================================
# Emission estimates
# ===========================================================================
def test_offline_estimate_matches_the_published_factor() -> None:
    api_clients.reset_caches()
    result = api_clients.estimate_transport_emissions("rail_highspeed", 1000.0, passengers=1)
    assert result.source == "offline_dataset"
    assert result.degraded is True
    assert result.data["kg_co2e_per_traveller"] == pytest.approx(14.0, abs=0.1)


def test_group_total_scales_with_passengers_but_per_head_does_not() -> None:
    api_clients.reset_caches()
    solo = api_clients.estimate_transport_emissions("coach", 500.0, passengers=1)
    group = api_clients.estimate_transport_emissions("coach", 500.0, passengers=4)
    assert group.data["kg_co2e_per_traveller"] == pytest.approx(solo.data["kg_co2e_per_traveller"])
    assert group.data["kg_co2e_total"] == pytest.approx(solo.data["kg_co2e_total"] * 4)


def test_flying_is_ranked_worse_than_rail_for_the_same_distance() -> None:
    """A sanity check on the direction of the whole product."""
    api_clients.reset_caches()
    rail = api_clients.estimate_transport_emissions("rail_highspeed", 800.0)
    flight = api_clients.estimate_transport_emissions("flight_short_haul", 800.0)
    assert flight.data["kg_co2e_per_traveller"] > rail.data["kg_co2e_per_traveller"] * 5


def test_unknown_mode_is_a_programming_error_not_a_silent_zero() -> None:
    with pytest.raises(KeyError):
        api_clients.estimate_transport_emissions("teleport", 100.0)


@pytest.mark.parametrize(
    ("distance_km", "expected_present", "expected_absent"),
    [
        (10.0, {"walking", "cycling"}, {"flight_short_haul", "rail_night"}),
        (500.0, {"rail_national", "coach", "rail_night"}, {"walking", "cycling"}),
        (5000.0, {"flight_long_haul"}, {"cycling", "coach", "flight_short_haul"}),
    ],
)
def test_only_physically_sensible_modes_are_offered(
    distance_km: float, expected_present: set[str], expected_absent: set[str]
) -> None:
    modes = set(api_clients.available_modes(distance_km))
    assert expected_present <= modes
    assert not (expected_absent & modes)


# ===========================================================================
# Climatiq adapter: the live path and, more importantly, the failure path
# ===========================================================================
@responses.activate
def test_climatiq_is_used_when_a_key_is_present(monkeypatch: pytest.MonkeyPatch) -> None:
    api_clients.reset_caches()
    monkeypatch.setattr(api_clients.SETTINGS, "climatiq_api_key", "test-key", raising=False)
    monkeypatch.setattr(api_clients.SETTINGS, "force_offline", False, raising=False)

    responses.add(
        responses.POST,
        "https://api.climatiq.io/data/v1/estimate",
        json={
            "co2e": 11.2,
            "co2e_unit": "kg",
            "emission_factor": {"name": "Rail, intl", "source": "Climatiq test", "year": 2024, "region": "EU"},
        },
        status=200,
    )

    result = api_clients.estimate_transport_emissions("rail_highspeed", 800.0)
    assert result.source == "climatiq"
    assert result.degraded is False
    assert result.data["kg_co2e_per_traveller"] == pytest.approx(11.2)


@responses.activate
def test_climatiq_failure_degrades_to_the_local_factor_instead_of_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The non-negotiable behaviour: an API outage must not break the chat."""
    api_clients.reset_caches()
    monkeypatch.setattr(api_clients.SETTINGS, "climatiq_api_key", "test-key", raising=False)
    monkeypatch.setattr(api_clients.SETTINGS, "force_offline", False, raising=False)

    responses.add(responses.POST, "https://api.climatiq.io/data/v1/estimate", status=503)

    result = api_clients.estimate_transport_emissions("coach", 300.0)
    assert result.source == "offline_dataset"
    assert result.degraded is True
    assert result.data["kg_co2e_per_traveller"] > 0
    assert any("Climatiq unavailable" in note for note in result.notes)


@responses.activate
def test_climatiq_gram_units_are_converted(monkeypatch: pytest.MonkeyPatch) -> None:
    api_clients.reset_caches()
    monkeypatch.setattr(api_clients.SETTINGS, "climatiq_api_key", "test-key", raising=False)
    monkeypatch.setattr(api_clients.SETTINGS, "force_offline", False, raising=False)
    responses.add(
        responses.POST,
        "https://api.climatiq.io/data/v1/estimate",
        json={"co2e": 11200.0, "co2e_unit": "g", "emission_factor": {}},
        status=200,
    )
    result = api_clients.estimate_transport_emissions("rail_highspeed", 800.0)
    assert result.data["kg_co2e_per_traveller"] == pytest.approx(11.2)


# ===========================================================================
# Accommodation
# ===========================================================================
def test_offline_accommodation_is_flagged_as_demonstration_data() -> None:
    api_clients.reset_caches()
    result = api_clients.fetch_accommodation(geo.geocode("Lisbon"), "2027-05-12", "2027-05-15", 2)
    assert result.degraded is True
    assert len(result.data) >= 3
    assert any(api_clients.DATA_PROVENANCE_NOTICE in note for note in result.notes)


def test_uncovered_destination_returns_empty_rather_than_inventing_hotels() -> None:
    api_clients.reset_caches()
    result = api_clients.fetch_accommodation(geo.geocode("Reykjavik"), "2027-05-12", "2027-05-15", 1)
    assert result.data == []
    assert any("does not cover" in note for note in result.notes)


# ===========================================================================
# Scoring
# ===========================================================================
def _option(mode: str, kg: float, cost: float, hours: float) -> eco_scoring.TransportOption:
    return eco_scoring.TransportOption(
        mode_key=mode, label=mode, icon="train", distance_km=500.0,
        kg_co2e_per_traveller=kg, kg_co2e_total=kg, cost_eur_per_traveller=cost,
        duration_h=hours, factor_source="test", data_source="offline_dataset",
    )


def test_strict_profile_prefers_the_cleanest_option() -> None:
    ranked = eco_scoring.score_transport_options(
        [_option("rail", 15, 90, 5), _option("flight", 180, 60, 3), _option("car", 90, 40, 7)],
        "strict",
    )
    assert ranked[0].mode_key == "rail"


def test_flexible_profile_can_prefer_a_cheaper_dirtier_option() -> None:
    ranked = eco_scoring.score_transport_options(
        [_option("rail", 15, 200, 9), _option("coach", 40, 25, 10)],
        "flexible",
    )
    assert ranked[0].mode_key == "coach"


def test_the_same_candidates_rank_differently_by_profile() -> None:
    """If the preference slot did not change the outcome it would be theatre."""
    candidates = lambda: [_option("rail", 15, 200, 9), _option("coach", 40, 25, 10)]  # noqa: E731
    strict = eco_scoring.score_transport_options(candidates(), "strict")[0].mode_key
    flexible = eco_scoring.score_transport_options(candidates(), "flexible")[0].mode_key
    assert strict != flexible


def test_options_over_budget_are_demoted_not_hidden() -> None:
    ranked = eco_scoring.score_transport_options(
        [_option("rail", 10, 400, 5), _option("coach", 45, 50, 9)], "strict", budget_eur=100
    )
    assert len(ranked) == 2, "an unaffordable option must still be visible"
    assert ranked[0].mode_key == "coach"
    assert any("budget" in note for note in ranked[1].notes)


def test_every_option_carries_a_rationale() -> None:
    ranked = eco_scoring.score_transport_options(
        [_option("rail", 15, 90, 5), _option("flight", 180, 60, 3)], "balanced"
    )
    assert all(option.rationale for option in ranked)


def test_bands_follow_the_documented_thresholds() -> None:
    assert eco_scoring.band_for(10) == "low"
    assert eco_scoring.band_for(60) == "moderate"
    assert eco_scoring.band_for(300) == "high"


def test_sleeper_fare_credit_is_capped_so_it_never_reads_as_free() -> None:
    cost, _ = eco_scoring.estimate_cost_and_duration("rail_night", 500.0)
    raw = 500.0 * 0.11
    assert 0 < cost, "a sleeper must never be priced at zero"
    assert cost >= raw * 0.4


def test_sleeper_gets_an_emissions_credit_for_the_avoided_hotel_night() -> None:
    assert eco_scoring.overnight_emissions_credit_kg("rail_night") == 12.0
    assert eco_scoring.overnight_emissions_credit_kg("rail_highspeed") == 0.0


def test_single_candidate_does_not_divide_by_zero() -> None:
    ranked = eco_scoring.score_transport_options([_option("rail", 15, 90, 5)], "strict")
    assert len(ranked) == 1 and ranked[0].score > 0


def test_empty_candidate_set_is_safe() -> None:
    assert eco_scoring.score_transport_options([], "strict") == []
    assert eco_scoring.score_accommodation([], "strict") == []


def test_audited_certification_outranks_self_declaration_on_a_strict_profile() -> None:
    ranked = eco_scoring.score_accommodation(
        [
            {"name": "Audited", "cert": "EU Ecolabel", "cert_tier": 1, "cert_status": "verified",
             "price_eur": 120, "energy": 0.9, "transit_min": 5, "local_sourcing": 0.7},
            {"name": "Self-declared", "cert": None, "cert_tier": 3, "cert_status": "none_claimed",
             "price_eur": 110, "energy": 0.2, "transit_min": 6, "local_sourcing": 0.2},
        ],
        "strict",
    )
    assert ranked[0]["name"] == "Audited"


def test_unknown_certification_is_scored_neutrally_not_as_absent() -> None:
    """Absence of evidence is not evidence of absence — and saying otherwise
    would be as dishonest as the greenwashing this assistant is meant to avoid."""
    ranked = eco_scoring.score_accommodation(
        [
            {"name": "Unknown", "cert": None, "cert_tier": None, "cert_status": "unknown",
             "price_eur": 100, "energy": None, "transit_min": 5, "local_sourcing": None},
            {"name": "Self-declared", "cert": None, "cert_tier": 3, "cert_status": "none_claimed",
             "price_eur": 100, "energy": None, "transit_min": 5, "local_sourcing": None},
        ],
        "strict",
    )
    assert ranked[0]["name"] == "Unknown"
    assert any("unverified" in note for note in ranked[0]["notes"])


def test_nightly_budget_split_leaves_room_for_the_rest_of_the_trip() -> None:
    nightly = eco_scoring.nightly_budget_from_total(1000.0, nights=4, transport_cost=200.0)
    assert nightly is not None
    assert nightly * 4 < 800.0
    assert eco_scoring.nightly_budget_from_total(None, 4, 200.0) is None


# ===========================================================================
# Handover
# ===========================================================================
@pytest.mark.parametrize(
    ("raw", "must_not_contain"),
    [
        ("email me at akif@example.com", "akif@example.com"),
        ("call +49 170 1234567", "1234567"),
        ("card 4111 1111 1111 1111", "4111"),
        ("passport AB1234567", "AB1234567"),
    ],
)
def test_contact_details_never_leave_in_an_escalation(raw: str, must_not_contain: str) -> None:
    assert must_not_contain not in handover.redact(raw)


def test_redaction_keeps_the_useful_content() -> None:
    cleaned = handover.redact("I'm flying to Lisbon, reach me at a@b.com")
    assert "Lisbon" in cleaned and "redacted-email" in cleaned


def test_payload_carries_everything_an_advisor_needs() -> None:
    events = [
        {"event": "user", "text": "I want to go to Lisbon",
         "parse_data": {"intent": {"name": "plan_trip", "confidence": 0.97}}},
        {"event": "bot", "text": "Where are you starting from?"},
        {"event": "user", "text": "Berlin, my email is x@y.com",
         "parse_data": {"intent": {"name": "inform", "confidence": 0.91}}},
    ]
    payload = handover.build_payload(
        slots={
            "origin": "Berlin", "destination": "Lisbon", "departure_date": "2027-05-12",
            "return_date": "2027-05-19", "travellers": 2.0, "budget": 800.0,
            "sustainability_level": "strict",
            "transport_options": [{"label": "High-speed rail", "kg_co2e_per_traveller": 39,
                                   "cost_eur_per_traveller": 444, "duration_h": 16, "score": 0.8,
                                   "mode_key": "rail_highspeed"}],
            "hotel_options": [],
        },
        events=events,
        reason="traveller_request",
        sender_id="test-session",
        data_source_mode="demo",
    )

    assert payload["reference"].startswith("ETA-")
    assert payload["trip_brief"]["destination"] == "Lisbon"
    assert payload["unresolved_fields"] == []
    assert len(payload["transcript"]) == 3
    assert "x@y.com" not in json.dumps(payload)
    assert payload["advisor_notes"]


def test_payload_names_what_is_still_missing() -> None:
    payload = handover.build_payload(
        slots={"destination": "Porto"}, events=[], reason="repeated_misunderstanding",
        sender_id="s", data_source_mode="demo",
    )
    assert "origin" in payload["unresolved_fields"]
    assert any("Intake incomplete" in note for note in payload["advisor_notes"])


def test_advisor_is_warned_when_no_option_fits_the_budget() -> None:
    payload = handover.build_payload(
        slots={
            "origin": "Berlin", "destination": "Lisbon", "departure_date": "2027-05-12",
            "return_date": "2027-05-19", "travellers": 1.0, "budget": 50.0,
            "sustainability_level": "balanced",
            "transport_options": [{"label": "High-speed rail", "cost_eur_per_traveller": 444,
                                   "kg_co2e_per_traveller": 39, "duration_h": 16, "score": 0.8,
                                   "mode_key": "rail_highspeed"}],
        },
        events=[], reason="traveller_request", sender_id="s", data_source_mode="demo",
    )
    assert any("under the stated budget" in note for note in payload["advisor_notes"])


def test_dispatch_falls_back_to_the_local_queue(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing is ever lost, even with the advisor webhook down."""
    queue = tmp_path / "handovers.jsonl"
    monkeypatch.setattr(handover.SETTINGS, "handover_webhook_url", None, raising=False)
    monkeypatch.setattr(handover.SETTINGS, "handover_queue_path", queue, raising=False)

    delivered, channel = handover.dispatch({"reference": "ETA-TEST", "trip_brief": {}})
    assert delivered is True and channel == "queue"
    assert json.loads(queue.read_text().strip())["reference"] == "ETA-TEST"
