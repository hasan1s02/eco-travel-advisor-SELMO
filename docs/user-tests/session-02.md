# Session P2 — 1 October 2026

**Format.** Self-operated. The participant used mouse and keyboard in a private browser
window (fresh session) and reported receiving no help.

**Consent.** Given in the survey: anonymised answers may be used in the report.

**Screener.** Thinks about travel emissions "sometimes".

**Raw data.** `raw/session-02-tracker.json` (158 tracker events) and
`raw/session-02-handover.jsonl`. Shared device coordinates were replaced with
`[redacted]` before the files were committed; nothing else was edited.

**Tasks.** The five protocol tasks were read aloud before the session.

**Path taken.** Greeting → trip intake (Berlin, shared location → Istanbul, 15–22 Oct,
€300, flexible) → transport comparison → card click → local experiences → trip summary →
offsets → human handover.

**Task completion (from the log).**

| Task | Outcome |
|---|---|
| 1 Plan a trip | Completed, with one recovery (F7). |
| 2 Choose an option and say why | Not recorded — the verbal answer was not noted. |
| 3 Find where the numbers come from | **No methodology request in the log.** The participant opened the trip summary and the offsets card, both of which carry provenance text, but never asked how figures were produced. |
| 4 Find somewhere to stay | **Not attempted.** No accommodation request in the log. |
| 5 Get a human | Completed, by typing "Talk to a human advisor". |

Task 3 is the protocol's predicted problem 4 ("nobody will ask about the methodology
unprompted") — and here it went unasked even when prompted. Transparency that has to be
requested was not requested. Whether the participant believed the summary and offset
footers already answered the task cannot be told from the log.

---

## Survey (1 = strongly disagree, 7 = strongly agree)

| # | Statement | Score |
|---|---|---|
| 1 | I found it easy to tell the assistant what I wanted. | 6 |
| 2 | I always knew what it expected from me next. | 7 |
| 3 | The travel options were easy to compare. | 6 |
| 4 | I could find what I needed without backtracking. | 7 |
| 5 | I believe the emission figures are roughly right. | 6 |
| 6 | The assistant was open about the limits of what it knows. | 6 |
| 7 | I would rely on this to make a real travel decision. | 7 |
| 8 | I felt the assistant was pushing me towards a particular answer. *(reverse-scored)* | 7 → 1 |
| 9 | I understood why it ranked the options the way it did. | 7 |

Ease of use (items 1–4): median 6.5. Trust (items 5–7, 8 reversed, 9): median 6.

**Open questions** (answered in Turkish; translated):

- *Doubt:* "Nothing."
- *Missing:* "Cheaper options could have come up — better value for money."
- *Description:* "It helps us compare many different ways of getting somewhere, and do as
  little harm to nature as possible."

---

## Observed in the log

| # | Observation | Evidence |
|---|---|---|
| F1 (repeat) | Transport-card click misread again. | 14:42:22 "Tell me more about travelling by petrol car (1 person)" → clarification. The night-train variant happened to classify as `ask_transport_options` and re-sent the whole comparison. |
| F7 | The destination quick reply arrived as a bare `/inform` with no city, twice. The bot answered "I couldn't find "/inform"". The participant recovered by typing "istanbul". | 14:41:01 and 14:41:12. Cause under investigation. |
| F8 | The greeting was sent twice at session start. | 14:40:53, two `/greet` events in the same second. |
| — | Relative dates ("in two weeks", "in three weeks") parsed correctly for both departure and return. | 14:41:45, 14:41:55. |

## Reading

Item 4 scored 7 although the log shows two failed button presses and a retyped destination.
The participant did not experience a typed recovery as backtracking. The survey alone would
have hidden F7; the log alone would have overstated its cost.

The description matches the intended positioning: comparison and lower impact, not a
booking site or a carbon calculator.

The "missing" answer asks for cheaper options from a participant who chose the *flexible*
profile, the one that weights cost most heavily (45%). Either the €300 budget was tight for
Berlin–Istanbul, or the cost weighting is not visible enough to feel like it is working.

Item 8 is the striking result: 7/7, the strongest possible "it pushed me", next to 7/7 on
"I would rely on it". Across both sessions, both participants felt pushed (5 and 7).
