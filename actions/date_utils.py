"""Tolerant natural-language date parsing for the trip intake form.

Rasa ships no date resolver out of the box; the usual answer is a Duckling
container, which the brief's zero-cost deployment target cannot justify. This
module is a deliberately small, fully tested substitute that covers the
phrasings travellers actually use when answering "when do you want to leave?".

It has no third-party dependencies, which keeps the action-server image small
and avoids the dependency conflict between Rasa 3.6's pinned ``regex``/``pytz``
and the versions required by ``dateparser``.
"""

from __future__ import annotations

import calendar
import re
from datetime import date, timedelta

__all__ = ["parse_travel_date", "format_date", "nights_between", "DateParseError"]


class DateParseError(ValueError):
    """Raised when a user utterance cannot be resolved to a calendar date."""


_MONTHS = {name.lower(): num for num, name in enumerate(calendar.month_name) if name}
_MONTHS.update({name.lower(): num for num, name in enumerate(calendar.month_abbr) if name})
_MONTHS.update({"sept": 9})

_WEEKDAYS = {name.lower(): num for num, name in enumerate(calendar.day_name)}
_WEEKDAYS.update({name.lower(): num for num, name in enumerate(calendar.day_abbr)})

_NUMBER_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12,
}

_ORDINAL_SUFFIX = re.compile(r"(?<=\d)(st|nd|rd|th)\b", re.I)
_NOISE = re.compile(
    r"\b(?:on|at|the|of|around|about|roughly|maybe|sometime|i|we|want|would|like|"
    r"to|leave|leaving|depart|departing|return|returning|come|back|home|travel|"
    r"travelling|go|going|please|date|is|will|be|am|'m)\b",
    re.I,
)


def _clean(text: str) -> str:
    text = text.strip().lower()
    text = _ORDINAL_SUFFIX.sub("", text)
    text = text.replace(",", " ")
    return re.sub(r"\s+", " ", text).strip()


def _resolve_year(month: int, day: int, today: date, year: int | None) -> int:
    """Pick the year a bare 'day month' most plausibly refers to.

    Travellers writing "12 May" in September mean next May, not last May, so an
    already-passed date rolls forward to the following year.
    """
    if year is not None:
        return year + 2000 if year < 100 else year
    candidate = date(today.year, month, min(day, calendar.monthrange(today.year, month)[1]))
    return today.year if candidate >= today else today.year + 1


def parse_travel_date(text: str, *, today: date | None = None) -> date:
    """Resolve a free-text travel date to a concrete ``datetime.date``.

    Raises :class:`DateParseError` when nothing sensible can be extracted, so
    the calling validator can ask the traveller to rephrase rather than
    silently booking the wrong month.
    """
    if text is None:
        raise DateParseError("no date given")

    today = today or date.today()
    raw = str(text)
    cleaned = _clean(raw)
    if not cleaned:
        raise DateParseError(f"could not read a date from {raw!r}")

    try:
        return _attempt(cleaned, today, raw)
    except DateParseError:
        # Second pass with filler words removed, so that "on the 15th of June"
        # and "I'd like to leave 12 May" resolve the same way as the bare date.
        stripped = re.sub(r"\s+", " ", _NOISE.sub(" ", cleaned)).strip()
        if stripped and stripped != cleaned:
            return _attempt(stripped, today, raw)
        raise


def _attempt(cleaned: str, today: date, raw: str) -> date:
    """Single parsing pass over an already-normalised utterance."""

    # --- ISO 8601: 2027-05-12 -------------------------------------------
    m = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", cleaned)
    if m:
        return _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)), raw)

    # --- Numeric with separators: 12/05/2027, 12.5.27 (day first) --------
    m = re.search(r"\b(\d{1,2})[/.](\d{1,2})(?:[/.](\d{2,4}))?\b", cleaned)
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        year = int(m.group(3)) if m.group(3) else None
        if 1 <= month <= 12:
            return _safe_date(_resolve_year(month, day, today, year), month, day, raw)

    # --- Relative keywords ------------------------------------------------
    if re.fullmatch(r"today|now|asap|right away", cleaned):
        return today
    if re.fullmatch(r"tomorrow|tmr|tmrw", cleaned):
        return today + timedelta(days=1)
    if re.fullmatch(r"day after tomorrow", cleaned):
        return today + timedelta(days=2)

    # "in three weeks", "in 10 days", "in 2 months"
    m = re.search(r"\bin (\d+|[a-z]+) (day|week|month)s?\b", cleaned)
    if m:
        qty_token = m.group(1)
        qty = int(qty_token) if qty_token.isdigit() else _NUMBER_WORDS.get(qty_token, 0)
        if qty:
            return _shift(today, qty, m.group(2))

    # "next week", "next month", "this weekend"
    m = re.search(r"\b(next|this) (week|month|weekend)\b", cleaned)
    if m:
        unit = m.group(2)
        if unit == "weekend":
            ahead = (calendar.SATURDAY - today.weekday()) % 7
            return today + timedelta(days=ahead or (0 if m.group(1) == "this" else 7))
        return _shift(today, 1 if m.group(1) == "next" else 0, unit) if m.group(1) == "next" else today

    # "next friday", "on monday"
    for name, index in _WEEKDAYS.items():
        if re.search(rf"\b{name}\b", cleaned):
            ahead = (index - today.weekday()) % 7
            if ahead == 0 or "next" in cleaned:
                ahead = ahead or 7
                if "next" in cleaned and ahead < 7:
                    ahead += 0
            return today + timedelta(days=ahead or 7)

    # --- "12 may 2027" / "12 may" ----------------------------------------
    m = re.search(r"\b(\d{1,2}) ([a-z]{3,9})\.? ?(\d{4})?\b", cleaned)
    if m and m.group(2) in _MONTHS:
        day, month = int(m.group(1)), _MONTHS[m.group(2)]
        year = int(m.group(3)) if m.group(3) else None
        return _safe_date(_resolve_year(month, day, today, year), month, day, raw)

    # --- "may 12 2027" / "may 12" ----------------------------------------
    m = re.search(r"\b([a-z]{3,9})\.? (\d{1,2})(?: (\d{4}))?\b", cleaned)
    if m and m.group(1) in _MONTHS:
        month, day = _MONTHS[m.group(1)], int(m.group(2))
        year = int(m.group(3)) if m.group(3) else None
        return _safe_date(_resolve_year(month, day, today, year), month, day, raw)

    # --- Bare month name: assume the 1st of the next such month ----------
    for name, month in _MONTHS.items():
        if re.fullmatch(rf"(?:early |mid |late )?{name}\.?(?: \d{{4}})?", cleaned):
            year_match = re.search(r"\b(\d{4})\b", cleaned)
            year = int(year_match.group(1)) if year_match else None
            day = 1 if "late" not in cleaned else 20
            if "mid" in cleaned:
                day = 15
            return _safe_date(_resolve_year(month, day, today, year), month, day, raw)

    raise DateParseError(f"could not read a date from {raw!r}")


def _shift(start: date, qty: int, unit: str) -> date:
    if unit == "day":
        return start + timedelta(days=qty)
    if unit == "week":
        return start + timedelta(weeks=qty)
    month_index = start.month - 1 + qty
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def _safe_date(year: int, month: int, day: int, raw: str) -> date:
    try:
        return date(year, month, day)
    except ValueError as exc:  # 31 February and friends
        raise DateParseError(f"{raw!r} is not a real calendar date") from exc


def format_date(value: date) -> str:
    """Render a date the way the assistant speaks it: 12 May 2027."""
    return f"{value.day} {calendar.month_name[value.month]} {value.year}"


def nights_between(departure: date, return_date: date) -> int:
    return max((return_date - departure).days, 0)
