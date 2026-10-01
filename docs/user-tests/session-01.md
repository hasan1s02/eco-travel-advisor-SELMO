# Session P1 — 1 October 2026

**Format.** Moderated, facilitator-operated. The participant made every decision and
dictated every free-text message; the facilitator operated mouse and keyboard. The
participant confirmed the typed phrases were their exact words, so language-level findings
are valid; findings about how a user *finds* controls are not, because the participant never
held the mouse.

**Consent.** Verbal and recorded in the survey: anonymised answers may be used in the report.

**Screener.** Thinks about travel emissions "sometimes" — the middle of the target spread.

**Raw data.** `raw/session-01-tracker.json` (172 tracker events, intents and confidences per
turn) and `raw/session-01-handover.jsonl` (the brief the human advisor received). Shared device coordinates were replaced with
`[redacted]` before the files were committed; nothing else was edited.

---

## Survey (1 = strongly disagree, 7 = strongly agree)

| # | Statement | Score |
|---|---|---|
| 1 | I found it easy to tell the assistant what I wanted. | 6 |
| 2 | I always knew what it expected from me next. | 5 |
| 3 | The travel options were easy to compare. | 6 |
| 4 | I could find what I needed without backtracking. | 4 |
| 5 | I believe the emission figures are roughly right. | 6 |
| 6 | The assistant was open about the limits of what it knows. | 5 |
| 7 | I would rely on this to make a real travel decision. | 6 |
| 8 | I felt the assistant was pushing me towards a particular answer. *(reverse-scored)* | 5 → 3 |
| 9 | I understood why it ranked the options the way it did. | 6 |

Ease of use (items 1–4): median 5.5. Trust (items 5–7, 8 reversed, 9): median 6.

**Open questions.** Doubt: "good chatbot". Missing feature and description: not answered.

---

## Observed in the log

| # | Observation | Evidence |
|---|---|---|
| F1 | Clicking a transport card breaks the conversation. The card sends "Tell me more about travelling by …", which no intent covers. | Turn 13:43:54 → `out_of_scope` at 1.000; turn 14:19:44 → `inform`, then clarification. Source: `frontend/src/components/Cards.tsx:116`. |
| F2 | A return date before the departure date was accepted and passed to the human advisor. | Handover ETA-9A9836CC: "2026-10-22 to 2026-10-18". |
| F3 | Answering the return-date question with "18 october 2026" erased the departure date. DIET tagged it `travel_date[role=departure]` and split "2026" into a second entity. | Turn 13:42:43; participant had to re-enter the departure date. |
| F5 | The two-stage clarification recovered the conversation as designed. After two misread card clicks the assistant offered constrained options; the participant picked accommodation and continued without escalating. | Turns 14:19:44 → 14:19:58 → `action_recommend_hotels`. |
| F6 | Every bot turn took about 2 s on the Windows development machine, against a 70 ms median measured in the Linux container. The UI showed 2,266 ms on the hotel turn — inside the 3 s requirement, but with little margin. Likely cause: `localhost` in `endpoints.yml` resolving to IPv6 first on Windows. To be confirmed. | Tracker timestamps; header latency badge in the participant's screenshot. |
| F4 | A departure-relative return ("one week later") was not understood and was classified out of scope with full confidence. | Turn 13:42:28 → `out_of_scope` 1.000. |

## Reading

The weakest item is 4 (backtracking, 4/7), and it is the one the log explains: F3 forced
the participant to answer the departure question twice, F4 forced a rephrase, and F1 ended
two exploration attempts in a misunderstanding. The survey and the log agree.

Trust is high (median 6), including item 7 ("would rely on this", 6) — given by a
participant whose handover brief contained an impossible date range (F2) that they did not
mention. High trust alongside an unnoticed error is a case for the design's transparency
commitments rather than evidence that they are working.

Item 8 (felt pushed, 5/7) is the notable result. The ranking is meant to inform, not steer;
a participant who only "sometimes" thinks about emissions read it as persuasion. Whether the
"best match" framing crosses from nudge into pressure is an ethical question for the report.

n = 1. These are observations, not findings that generalise.
