"""Human-advisor escalation with full conversation context.

Section 2 of the brief requires a "human advisor escalation module with full
context handover". The payload built here is what an advisor needs to pick the
conversation up cold: the structured trip brief, the recommendations already
shown, the reason for escalation, and a readable transcript.

Data-protection note (GDPR, Art. 5(1)(c) data minimisation): the transcript is
truncated to the current planning session, free-text is passed through
:func:`redact`, and nothing is written anywhere unless an escalation actually
happens.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import requests

from .config import HTTP_TIMEOUT_SECONDS, SETTINGS

logger = logging.getLogger(__name__)

# Patterns that should never leave the assistant in an escalation payload.
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b")
_PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)")
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
_PASSPORT = re.compile(r"\b[A-Z]{1,2}\d{6,9}\b")

TRANSCRIPT_TURN_LIMIT = 40


def redact(text: str | None) -> str:
    """Strip contact and identity details from free text before it is stored."""
    if not text:
        return ""
    cleaned = _CARD.sub("[redacted-number]", str(text))
    cleaned = _EMAIL.sub("[redacted-email]", cleaned)
    cleaned = _PHONE.sub("[redacted-phone]", cleaned)
    cleaned = _PASSPORT.sub("[redacted-id]", cleaned)
    return cleaned


def build_transcript(events: list[dict[str, Any]], limit: int = TRANSCRIPT_TURN_LIMIT) -> list[dict[str, str]]:
    """Readable user/bot transcript from the raw Rasa tracker events."""
    transcript: list[dict[str, str]] = []
    for event in events:
        if event.get("event") == "user" and event.get("text"):
            transcript.append(
                {
                    "speaker": "traveller",
                    "text": redact(event["text"]),
                    "intent": (event.get("parse_data") or {}).get("intent", {}).get("name", ""),
                    "confidence": round(
                        float((event.get("parse_data") or {}).get("intent", {}).get("confidence") or 0.0), 3
                    ),
                }
            )
        elif event.get("event") == "bot" and event.get("text"):
            transcript.append({"speaker": "advisor_bot", "text": str(event["text"])[:600]})
    return transcript[-limit:]


def build_payload(
    *,
    slots: dict[str, Any],
    events: list[dict[str, Any]],
    reason: str,
    sender_id: str,
    data_source_mode: str,
) -> dict[str, Any]:
    """Assemble the complete escalation package."""
    reference = f"ETA-{uuid.uuid4().hex[:8].upper()}"

    transport = slots.get("transport_options") or []
    hotels = slots.get("hotel_options") or []

    unresolved = [
        name
        for name in ("destination", "origin", "departure_date", "return_date", "budget", "sustainability_level")
        if not slots.get(name)
    ]

    return {
        "reference": reference,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "escalation_reason": reason,
        "conversation_id": sender_id,
        "data_source_mode": data_source_mode,
        "trip_brief": {
            "origin": slots.get("origin"),
            "destination": slots.get("destination"),
            "departure_date": slots.get("departure_date"),
            "return_date": slots.get("return_date"),
            "travellers": slots.get("travellers"),
            "budget_eur": slots.get("budget"),
            "sustainability_level": slots.get("sustainability_level"),
            "offset_interest": slots.get("offset_interest"),
            "distance_km": slots.get("trip_distance_km"),
        },
        "unresolved_fields": unresolved,
        "recommendations_shown": {
            "transport": [
                {
                    "label": o.get("label"),
                    "kg_co2e_per_traveller": o.get("kg_co2e_per_traveller"),
                    "cost_eur_per_traveller": o.get("cost_eur_per_traveller"),
                    "duration_h": o.get("duration_h"),
                    "rank_score": o.get("score"),
                }
                for o in transport[:5]
            ],
            "accommodation": [
                {"name": h.get("name"), "cert": h.get("cert"), "price_eur": h.get("price_eur"), "rank_score": h.get("score")}
                for h in hotels[:5]
            ],
        },
        "transcript": build_transcript(events),
        "advisor_notes": _advisor_notes(slots, unresolved, transport),
    }


def _advisor_notes(slots: dict[str, Any], unresolved: list[str], transport: list[dict[str, Any]]) -> list[str]:
    """Short prompts telling the advisor where the bot's limits were reached."""
    notes: list[str] = []
    if unresolved:
        notes.append("Intake incomplete — still missing: " + ", ".join(unresolved) + ".")
    if slots.get("sustainability_level") == "strict" and transport:
        best = transport[0]
        if str(best.get("mode_key", "")).startswith("flight"):
            notes.append(
                "Traveller asked for the strictest profile but the best-scoring option is still a flight. "
                "Worth checking manually whether an overland routing exists that the distance heuristics missed."
            )
    if slots.get("budget") and transport:
        affordable = [o for o in transport if (o.get("cost_eur_per_traveller") or 0) <= slots["budget"]]
        if not affordable:
            notes.append("No option came in under the stated budget. Budget or dates likely need to move.")
    if not notes:
        notes.append("No blocking issues detected; the traveller asked for a person by choice.")
    return notes


def dispatch(payload: dict[str, Any]) -> tuple[bool, str]:
    """Send the payload to the advisor desk.

    Returns ``(delivered, channel)``. A webhook failure is not fatal: the
    payload is appended to a local queue so nothing is lost, and the traveller
    is told which of the two happened.
    """
    if SETTINGS.handover_webhook_url:
        try:
            response = requests.post(
                SETTINGS.handover_webhook_url,
                json=payload,
                timeout=HTTP_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return True, "webhook"
        except Exception as exc:
            logger.warning("Handover webhook failed (%s); writing to local queue", exc)

    try:
        SETTINGS.handover_queue_path.parent.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS.handover_queue_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return True, "queue"
    except Exception as exc:  # pragma: no cover - disk failure
        logger.error("Could not persist handover payload: %s", exc)
        return False, "none"
