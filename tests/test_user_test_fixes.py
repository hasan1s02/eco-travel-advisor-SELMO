"""Regression tests for the defects found in user testing (docs/user-tests/).

Each test names the finding it covers, so the report can trace every change
from observation to verification.
"""

from __future__ import annotations

import asyncio
from datetime import date

import pytest
from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher

from actions.actions import ValidateTripForm
from actions.date_utils import DateParseError, parse_return_date

DEPARTURE = date(2027, 5, 12)


def _tracker(slots: dict, events: list[dict] | None = None) -> Tracker:
    return Tracker(
        sender_id="test",
        slots=slots,
        latest_message={"text": "", "intent": {"name": "inform"}, "entities": [], "metadata": {}},
        events=events or [],
        paused=False,
        followup_action=None,
        active_loop={"name": "trip_form"},
        latest_action_name="trip_form",
    )


def _slot(name: str, value) -> dict:
    return {"event": "slot", "name": name, "value": value}


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# F4 — "one week later" was not understood as a return date
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("utterance", "expected"),
    [
        ("one week later", date(2027, 5, 19)),
        ("a week later", date(2027, 5, 19)),
        ("3 days later", date(2027, 5, 15)),
        ("five nights", date(2027, 5, 17)),
        ("for two weeks", date(2027, 5, 26)),
        ("10 days after", date(2027, 5, 22)),
    ],
)
def test_f4_stay_length_is_read_relative_to_departure(utterance: str, expected: date) -> None:
    assert parse_return_date(utterance, DEPARTURE) == expected


def test_f4_today_relative_phrases_still_count_from_today() -> None:
    """P2 answered "in three weeks" meaning from today; that must not change."""
    today = date(2026, 10, 1)
    assert parse_return_date("in three weeks", date(2026, 10, 15), today=today) == date(2026, 10, 22)


def test_f4_absolute_dates_are_unaffected() -> None:
    assert parse_return_date("19 May 2027", DEPARTURE) == date(2027, 5, 19)


def test_f4_without_a_departure_a_stay_length_is_not_guessed() -> None:
    with pytest.raises(DateParseError):
        parse_return_date("one week later", None)


# ---------------------------------------------------------------------------
# F3 — answering the return question erased the departure date
# ---------------------------------------------------------------------------
def test_f3_departure_survives_a_misread_entity_during_the_return_question() -> None:
    tracker = _tracker(
        slots={"requested_slot": "return_date", "departure_date": "2026"},
        events=[_slot("departure_date", "2027-05-12"), _slot("departure_date", "2026")],
    )
    dispatcher = CollectingDispatcher()
    result = _run(ValidateTripForm().validate_departure_date("2026", dispatcher, tracker, {}))
    assert result == {"departure_date": "2027-05-12"}
    assert dispatcher.messages == []  # no confusing "couldn't read that" message


def test_f3_departure_is_still_validated_when_it_is_the_question_being_asked() -> None:
    tracker = _tracker(slots={"requested_slot": "departure_date"}, events=[])
    result = _run(ValidateTripForm().validate_departure_date("12 May 2027", CollectingDispatcher(), tracker, {}))
    assert result == {"departure_date": "2027-05-12"}


# ---------------------------------------------------------------------------
# F2 — a return date before departure reached the human advisor
# ---------------------------------------------------------------------------
def test_f2_a_later_departure_clears_an_earlier_return() -> None:
    tracker = _tracker(
        slots={"requested_slot": "departure_date", "return_date": "2027-05-18"},
        events=[_slot("return_date", "2027-05-18")],
    )
    dispatcher = CollectingDispatcher()
    result = _run(ValidateTripForm().validate_departure_date("22 May 2027", dispatcher, tracker, {}))
    assert result == {"departure_date": "2027-05-22", "return_date": None}
    assert "cleared" in dispatcher.messages[0]["text"]


def test_f2_return_before_departure_is_still_rejected() -> None:
    tracker = _tracker(slots={"requested_slot": "return_date", "departure_date": "2027-05-22"})
    result = _run(ValidateTripForm().validate_return_date("18 May 2027", CollectingDispatcher(), tracker, {}))
    assert result == {"return_date": None}


def test_f4_validator_uses_the_stay_length() -> None:
    tracker = _tracker(slots={"requested_slot": "return_date", "departure_date": "2027-05-12"})
    result = _run(ValidateTripForm().validate_return_date("one week later", CollectingDispatcher(), tracker, {}))
    assert result == {"return_date": "2027-05-19"}


# ---------------------------------------------------------------------------
# F7 — a button payload with no city was searched for as a place
# ---------------------------------------------------------------------------
def test_f7_a_bare_payload_is_not_treated_as_a_city_name() -> None:
    dispatcher = CollectingDispatcher()
    result = _run(
        ValidateTripForm().validate_destination("/inform", dispatcher, _tracker({"requested_slot": "destination"}), {})
    )
    assert result == {"destination": None}
    assert "/inform" not in dispatcher.messages[0]["text"]


# ---------------------------------------------------------------------------
# F9 — buttons sent from custom actions carried doubled braces
# ---------------------------------------------------------------------------
def test_f9_custom_action_buttons_carry_parseable_payloads() -> None:
    """Custom-action buttons skip Rasa's template formatter, so '{{' stays '{{'."""
    dispatcher = CollectingDispatcher()
    _run(ValidateTripForm().validate_destination("Atlantis", dispatcher, _tracker({"requested_slot": "destination"}), {}))
    payloads = [b["payload"] for b in dispatcher.messages[0]["buttons"]]
    assert '/inform{"city": "Lisbon"}' in payloads
    assert not any("{{" in p for p in payloads)
