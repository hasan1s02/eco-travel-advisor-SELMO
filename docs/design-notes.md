# Design notes

Why the assistant behaves as it does, what its numbers mean, and where it falls short.

## Three design commitments

The assistant is built around three rules, and most of the code exists to keep them:

**It never fails loudly.** Every outbound call is wrapped. A Climatiq outage falls back to
the bundled DESNZ/DEFRA conversion factors; an Amadeus failure falls back to the curated
dataset. The conversation continues and the user is told what changed.

**It never claims more certainty than the data supports.** Estimates are called estimates.
Demonstration data is labelled as demonstration data on the card itself. A property whose
certification the supplier does not publish is shown as *unverified*, not as *uncertified* —
absence of evidence is not evidence of absence, and conflating the two would be the exact
greenwashing the assistant exists to counter. `action_explain_methodology` will show its
working, and its limitations, at any point in any conversation.

**It always leaves a route to a human.** `/request_human_agent` wins from anywhere,
including mid-form. If a rephrase and a set of constrained options both fail, the third misunderstanding
escalates on its own rather than looping.

---

## How the numbers are produced

**Emissions** = route distance × emission factor per passenger-kilometre.

Factors come from the UK DESNZ/DEFRA 2023 conversion factors, cross-checked against the
EEA's rail-versus-air figures, and are replaced by live Climatiq values when a key is set.
Straight-line distance is multiplied by a route-circuity factor — 1.20 rail, 1.25 road,
1.35 ferry, 1.05 air plus a 40 km routing allowance — because networks do not run in
straight lines. Sleeper services receive a credit for the hotel night they replace, in both
cost and emissions, capped so a sleeper can never appear free.

**Ranking** is a weighted sum of min–max normalised criteria, with weights set by the
traveller's declared priority:

| Priority | Emissions | Cost | Journey time |
|---|---|---|---|
| Strict | 65% | 15% | 20% |
| Balanced | 40% | 30% | 30% |
| Flexible | 20% | 45% | 35% |

Plain min–max normalisation has a pathology worth naming: when candidates barely differ on
a criterion, the tiny spread is stretched across the whole [0, 1] range and a meaningless
difference gets full weight — a nine-hour train would beat a ten-hour coach on journey time
as decisively as a one-hour flight beats a two-day drive. `eco_scoring.py` therefore applies
**relative-spread damping**: where the range is small relative to the mean, scores are
pulled back toward indifference. Affordability is handled as a hard constraint rather than
a weight — an option over budget ranks below every affordable one, but stays visible, so the
trade-off between budget and emissions is never hidden.

Accommodation is ranked on certification credibility (audited against a GSTC-recognised
standard > third-party audited > self-declared), renewable electricity share, walking
distance to transit, local sourcing and price.

**What these numbers are not.** Fleet averages, not measurements of a specific journey.
Accommodation emissions use a flat 12 kg per person per night, a rough European hotel
average and nothing more. The assistant says all of this when asked, and the UI carries a
provenance line on every card.

---

## Measured results

| Measure | Result | Method |
|---|---|---|
| Intent classification | 0.775 accuracy | 5-fold cross-validation, 868 examples, 21 intents |
| Intent classification | 0.782 accuracy | 80/20 holdout, seed 42 |
| Entity extraction | 0.982 accuracy | 5-fold cross-validation |
| Dialogue — conversations | 14 / 14 | End-to-end test stories, real NLU in the loop |
| Dialogue — action turns | 75 / 75 | Same run |
| Unit tests | 84 / 84 | pytest, external APIs mocked |
| User testing | 2 sessions, 7 defects fixed | `docs/user-tests/`, findings log in the protocol |
| Latency | median 70 ms, p95 108 ms | 49 live turns through the REST channel |

The intent figure is 0.78, not higher, and `docs/evaluation.md` explains why rather than
explaining it away: three measured iterations took it from 0.67 to 0.78 and then flat, with
every targeted intent improving and the improvement paid for by its neighbours. The causes
are an open-ended `out_of_scope` class and one-to-three-word social intents that DIET
classifies without dialogue context. Dialogue accuracy is nonetheless 1.000, because most of
the remaining confusions map to the same action.

The end-to-end stories in `tests/test_stories.yml` deliberately use wordings that do **not**
appear in `data/nlu.yml` — a test the model has memorised proves nothing.

## Project layout

```
.
├── config.yml                  spaCy + DIET pipeline, policies, fallback thresholds
├── domain.yml                  intents, entities with roles, slots, form, responses
├── data/
│   ├── nlu.yml                 868 annotated examples, lookup tables, synonyms
│   ├── stories.yml             happy paths, interruptions, recovery, escalation
│   └── rules.yml               deterministic behaviour (greetings, escalation, form)
├── actions/
│   ├── actions.py              the Rasa custom actions
│   ├── api_clients.py          Climatiq / Amadeus adapters with offline fallbacks
│   ├── eco_scoring.py          the weighted multi-criteria ranking function
│   ├── geo.py                  geocoding, reverse geocoding, route distances
│   ├── date_utils.py           dependency-free natural-language date parsing
│   ├── handover.py             escalation payload, PII redaction, delivery
│   └── data/                   emission factors, gazetteer, properties, experiences
├── frontend/                   React 18 + TypeScript + Vite on the Rasa REST channel
├── tests/                      pytest unit tests + end-to-end conversation tests
├── scripts/                    serve.sh, demo transcripts, metrics summariser
├── docs/
│   ├── architecture.md         system and request-path diagrams
│   ├── conversation-flows.md   dialogue flows, UI mapping, accessibility
│   ├── evaluation.md           what the numbers mean and what they don't
│   ├── user-testing-protocol.md  usability study and findings log
│   ├── user-tests/             two recorded sessions (survey + conversation log)
│   ├── metrics/                raw rasa test output + generated RESULTS.md
│   └── transcripts/            seven recorded conversations with latencies
├── deploy/huggingface/         single-container Spaces deployment
└── docker-compose.yml          rasa + actions + frontend
```

## Why the pipeline looks like this

`SpacyNLP` + `SpacyFeaturizer` contribute pre-trained 300-dimension word vectors, which
carry entity recognition for city names that appear only two or three times in the training
data. `RegexFeaturizer` feeds the lookup tables to DIET as sparse features **instead of**
`RegexEntityExtractor`, which cannot assign entity roles — and this assistant depends on
distinguishing `city[role=origin]` from `city[role=destination]`, so DIET has to own
extraction outright.

A DistilBERT variant is kept in `config_distilbert.yml`. It is not the default: a
transformer encoder adds inference cost on a CPU-only host against the three-second
response requirement, while the error analysis in `docs/evaluation.md` puts the remaining
NLU errors in overlapping short intents rather than encoder capacity. The two pipelines
have not been benchmarked against each other.

Error recovery deliberately has **two independent routes**, because measurement showed one
is not enough. `FallbackClassifier` at threshold 0.60 catches low-confidence NLU — but DIET
with `constrain_similarities` is badly calibrated and returned 1.000 confidence for pure
keyboard mash, so that threshold almost never fires in practice. Nonsense is therefore also
trained explicitly as `out_of_scope`, and the RulePolicy core fallback catches whatever
reaches an unmodelled dialogue state. `UnexpecTEDIntentPolicy` was trialled as a third
route and removed; `config.yml` records why.

---

## Data protection

Personal data is limited to what the trip needs: origin, destination, dates, group size,
budget and sustainability preference. Shared GPS coordinates are rounded to two decimal
places **in the browser before transmission** — roughly 1 km, enough to identify a city and
not a household.

Conversations are held only in server memory and are never written to disk except on
escalation. A new session starts after 60 minutes of inactivity, but Rasa's in-memory
tracker keeps earlier turns until the server restarts — longer than intended, and a gap
against GDPR storage limitation that a scheduled purge would close. Nothing leaves
the assistant except on escalation, and escalation payloads pass through `handover.redact()`,
which strips email addresses, phone numbers, card-length digit strings and passport-shaped
identifiers before dispatch. `action_explain_privacy` states all of this on request. "Start over" clears the trip
details; it does not delete the conversation log, which only a restart removes.

---

## Known limitations

Honest ones, since the assistant is built on the premise that stating limitations matters:

- **Distance heuristics, not itineraries.** Route circuity is a multiplier, not a timetable
  lookup. Over ~1500 km the overland figures assume a multi-leg journey and will differ from
  a real booking. A route with an awkward connection may be ranked better than it deserves.
- **Accommodation emissions are a flat rate.** 12 kg per person per night ignores the
  property's own energy mix, which the assistant otherwise ranks on. It is a known
  inconsistency, kept because no free source provides per-property figures.
- **The gazetteer is European and city-level.** 78 cities, no regions, no rural
  destinations — the geographic scope of the evaluation, and a real limit on the product.
- **Certification data is synthetic.** Every property name in `eco_hotels.json` is invented.
  The scheme names are real; their attachment to these properties is illustrative.
- **English only** in the NLU model. The UI takes dictation in the browser's locale, but the
  assistant will not understand it unless it is English.
- **User testing is small.** Two sessions (`docs/user-tests/`) found seven defects, all
  fixed, but two participants support observations, not general claims. Both felt the
  assistant pushed them towards an answer; that is reported, not yet resolved.
- **Intent classification sits at 0.78**, and the ceiling is structural rather than a
  training-budget problem. `docs/evaluation.md` has the analysis.

---
