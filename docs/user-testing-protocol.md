# User testing protocol

Section 5 of the assignment brief asks for usability testing with a small group of potential
travellers, measuring "perceived trust and ease-of-use through surveys or interviews", and
for the insights to be incorporated into the final evaluation.

This document is the instrument: run it as written, and the results drop straight into the
report. It is designed for **five to eight participants**, which is where think-aloud testing
stops returning new usability problems for a single interface of this size.

---

## Before the session

Have the stack running (`docker compose up`, or `scripts/serve.sh start` plus the Vite dev
server) and open at `http://localhost:3000`. Use a fresh browser profile per participant so
no earlier conversation is in `sessionStorage`.

Record the screen if the participant consents. Do not record faces or audio identifying
them; you need what they clicked and what they said, nothing more.

**Screener.** Recruit people who have taken at least one leisure trip in the past year.
Aim for a spread on one axis that matters here: how much they already think about travel
emissions. Three people who already take the train everywhere will tell you nothing about
whether the assistant persuades anyone.

**Brief to read aloud:**

> This is a prototype travel assistant. I'm testing the software, not you — if something is
> confusing, that's a finding I need. Please think out loud: say what you're looking at,
> what you expect to happen, and what surprises you. I won't be able to help you during the
> tasks, but I'll answer anything afterwards.
>
> The numbers it shows are demonstration data, not real bookings.

---

## Tasks

Give one at a time. Do not read out any interface wording — if the participant cannot find
something, that is the result.

**Task 1 — Plan a trip (target: under 4 minutes).**
> You want a long weekend somewhere in Europe in May. Use the assistant to plan it.

Watch for: do they type or use the quick replies? Do they understand the sustainability
priority question, or do they pick one at random? Does the date question cause hesitation?

**Task 2 — Interpret the comparison (target: under 1 minute).**
> Looking at the travel options it just gave you, which one would you choose, and why?

Watch for: do they read the CO₂e figure, the cost, or the "best match" badge first? Do they
notice the colour bands? Do they mention the ranking rationale text at all?

**Task 3 — Challenge it.**
> You're not sure you believe the emissions numbers. Find out where they come from.

Watch for: do they think to ask? Do they find `action_explain_methodology` by typing, or
only via the quick reply? After reading it, does their confidence go up or down — and note
that **down can be the right answer**, if the disclosure made a real limitation visible.

**Task 4 — Get a human.**
> You've decided this needs a person. Get yourself transferred.

Watch for: time to find the route, and whether they believe the handover actually happened.

**Task 5 — Accommodation, with a catch.**
> Find somewhere to stay. One of these properties has an unverified certification — which,
> and does that change your choice?

Watch for: whether the *unverified* badge is read as "not certified" (a failure of the
design's central honesty claim) or as "not confirmed either way" (the intent).

---

## Post-task survey

Seven-point Likert, 1 = strongly disagree, 7 = strongly agree. Items 1–4 are ease of use,
items 5–9 trust. Item 8 is reverse-scored.

| # | Statement |
|---|---|
| 1 | I found it easy to tell the assistant what I wanted. |
| 2 | I always knew what it expected from me next. |
| 3 | The travel options were easy to compare. |
| 4 | I could find what I needed without backtracking. |
| 5 | I believe the emission figures are roughly right. |
| 6 | The assistant was open about the limits of what it knows. |
| 7 | I would rely on this to make a real travel decision. |
| 8 | I felt the assistant was pushing me towards a particular answer. |
| 9 | I understood why it ranked the options the way it did. |

**Three open questions:**

1. What, if anything, made you doubt what it told you?
2. What would you have wanted it to do that it could not?
3. If a friend asked, how would you describe what this thing is for?

Question 3 is the sharpest one in the set. If participants describe it as "a booking site"
or "a carbon calculator", the positioning has failed regardless of how the Likert items
score.

---

## Analysing the results

Report the median and range per item, not the mean — with n ≈ 6 a single outlier drags a
mean around and implies precision the sample cannot support.

Separate the two constructs. **Ease of use** and **trust** come apart, and the interesting
case is high ease with low trust: an assistant that is pleasant to use and not believed is
a worse outcome than a clunky one that is, because it will be used and then ignored.

Pair every Likert score with an observed behaviour from the think-aloud. "Item 5 scored 6"
means little on its own; "item 5 scored 6, and four of six participants said the phrase
'demonstration data' was what convinced them the figures were not invented" is a finding.

Count **task success**, **time on task** and **assists** (times you had to intervene)
separately per task. An assist is a failure of the interface, and the tasks above are
ordered so that assists in tasks 3–5 are the ones that matter most: they are the
transparency and escalation paths, which are the design's actual claims.

---

## Incorporating the findings

The brief requires at least one design change driven by testing. Record it in this format,
so the report can quote it directly:

> **Finding.** _(what was observed, with how many participants)_
> **Evidence.** _(a quote or a behaviour, not an interpretation)_
> **Change.** _(the specific file and what was altered)_
> **Verification.** _(how you confirmed the change worked — a re-test, a screenshot, a test case)_

### Findings log

_Fill this in as sessions are run. One entry per change._

| # | Finding | Participants affected | Change made | Verified |
|---|---|---|---|---|
| 1 | | / | | |
| 2 | | / | | |
| 3 | | / | | |

---

## Predicted problem areas

Recorded before testing, so that hindsight cannot quietly reshape them afterwards. Being
wrong about these is a finding too.

1. **The sustainability priority question is abstract.** "Strict / balanced / flexible"
   asks people to state a trade-off before seeing anything to trade off. Expect hesitation
   and near-random selection. If confirmed, the fix is to ask it *after* a first comparison
   rather than during intake.
2. **"Unverified" will be read as "uncertified".** The distinction is the design's central
   honesty claim and it rests on one word in a badge.
3. **The ranking will surprise people.** A coach can outrank a train that has both lower
   emissions and a shorter journey, because it is much cheaper — correct multi-criteria
   behaviour that looks like a bug. The per-option rationale exists for exactly this moment;
   testing will show whether anyone reads it.
4. **Nobody will ask about the methodology unprompted.** Task 3 has to tell them to. If so,
   transparency that must be requested is transparency most users never receive, and the
   design needs to surface a short version unprompted.
