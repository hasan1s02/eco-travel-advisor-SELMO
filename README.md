# Eco-Travel Advisor

A conversational agent for sustainable tourism planning, built on Rasa Open Source.

It helps a traveller plan a trip with a materially smaller carbon footprint: it compares
transport options by estimated emissions, cost and journey time; ranks eco-certified
accommodation; suggests low-impact, community-benefiting activities; and hands the
conversation to a human advisor — with full context — whenever it reaches its limits.

*MSc Artificial Intelligence · Advanced Conversational UI Design and Chatbot Development ·
BSBI / University for the Creative Arts.*

---

## What it does

| Capability | Where it lives |
|---|---|
| Adaptive multi-turn intake (destination, origin, dates, group, budget, sustainability priority) | `trip_form` + `ValidateTripForm` |
| Emission estimates per transport mode, live or offline | `actions/api_clients.py` |
| Live flight fares and hotel availability (Amadeus), estimates as fallback | `actions/api_clients.py` |
| Weighted ranking that changes with the traveller's stated priority | `actions/eco_scoring.py` |
| Eco-certified accommodation with honest certification status | `actions/api_clients.py` |
| Location by typed city name or shared GPS | `actions/geo.py` |
| Human escalation with a redacted, complete brief | `actions/handover.py` |
| Two-stage clarification before escalating | `ActionTwoStageClarification` |
| Colour-coded result cards, carousels, quick replies, handover indicator | `frontend/src/components/Cards.tsx` |

### Three design commitments

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

## Quick start

### Option A — Docker (recommended, needs no local Python)

```bash
git clone https://github.com/hasan1s02/eco-travel-advisor-SELMO.git eco-travel-advisor
cd eco-travel-advisor

cp .env.example .env                               # optional: keys can stay blank
docker compose --profile train run --rm train      # once, ~15 min
docker compose up --build
```

Open **http://localhost:3000**.

On Windows, run exactly the same two commands in PowerShell.

The trained model is git-ignored (~36 MB), so it has to be produced once before
the stack starts. The `train` profile does that inside a container, which is why
this path needs no Python on the host — and that matters more than it sounds:
Rasa 3.6 pins TensorFlow 2.12, which ships no wheels for Python 3.11 or newer.
On a machine with only 3.11+ installed, `pip install rasa` fails outright, pip
falls back to building spaCy from source, and the build dies in the Cython
compiler. Pinning `python:3.10-slim` in the images removes the whole class of
problem.

### Option B — local, three terminals

Requires **Python 3.10** on the host. Check with `python3.10 --version`
(`py -3.10 --version` on Windows) before starting; if it is missing, use
Option A rather than installing another Python.

```bash
python3.10 -m venv .venv && source .venv/bin/activate   # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements-rasa.txt

rasa train --fixed-model-name eco_travel_advisor

# terminal 1
rasa run actions --actions actions.actions
# terminal 2
rasa run --enable-api --cors "*"
# terminal 3
cd frontend && npm install && npm run dev
```

Python **3.10** specifically. `requirements-rasa.txt` pins Rasa and the spaCy
English pipeline together; it is the same file the Docker images install, so
both paths resolve to an identical dependency set.

For a quick check with no frontend at all: `rasa shell` (with the action server running).

### Windows, step by step

The two things that go wrong on Windows are both version problems, so check
them first:

```powershell
py -0                 # which Python versions are installed
node --version        # needed for the frontend only
```

If `py -0` does not list a 3.10, install one. It sits alongside 3.11/3.12/3.13
without disturbing them — the `py` launcher picks the version you ask for:

```powershell
winget install -e --id Python.Python.3.10
winget install -e --id OpenJS.NodeJS.LTS     # only if node is missing
```

Close and reopen PowerShell, then:

```powershell
cd C:\path\to\eco-travel-advisor

py -3.10 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass   # allows the activate script
.\.venv\Scripts\Activate.ps1

pip install -r requirements-rasa.txt
rasa train --fixed-model-name eco_travel_advisor
```

Then three PowerShell windows, each with the venv activated:

```powershell
rasa run actions --actions actions.actions          # window 1
rasa run --enable-api --cors "*"                    # window 2
cd frontend ; npm install ; npm run dev             # window 3
```

**Do not** run `pip install rasa` against Python 3.11 or newer. It fails with
"no matching distribution" — Rasa 3.6 pins TensorFlow 2.12, which has no wheels
for 3.11+ — and pip then tries to build spaCy from source and dies in the Cython
compiler. The error is long and looks like a compiler problem; it is a Python
version problem.

---

---

## API keys

**Every key is optional.** With none configured the assistant runs entirely on the bundled
datasets in `actions/data/` and says so on every card. That is the configuration this
submission was developed and evaluated in.

| Service | Purpose | Free tier | Without it |
|---|---|---|---|
| [Climatiq](https://www.climatiq.io/) | Live emission factors | 500 calls/month | DESNZ/DEFRA 2023 factors, bundled |
| [Amadeus](https://developers.amadeus.com/) | Hotel availability, flight fares | **Closed** — see below | Curated property set; distance-based fare estimate |
| [OpenCage](https://opencagedata.com/) | Geocoding, reverse geocoding | 2,500 req/day | 78-city offline gazetteer |
| [OpenRouteService](https://openrouteservice.org/) | Road distances | 2,000 req/day | Circuity-adjusted great-circle |

No free API publishes hotel eco-certification status, which the assignment brief notes and
which the design works around: certification comes from the curated dataset, and any live
property not on that list is displayed as *unverified*.

**Amadeus no longer issues keys.** Amadeus paused self-service registration in March
2026 and switched off every self-service key on 17 July 2026. The hotel and flight adapters
are written against the documented sandbox API and tested with mocked responses, but
they can no longer run live; the fallback path is the one every deployment now takes.

Keys go in `.env` (git-ignored) and are read only by the action server — the one container
that is never published to the host.

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

## Testing

```bash
# Unit tests — 84 cases over parsing, geocoding, API fallbacks, scoring, redaction,
# plus regression tests for every defect found in user testing
ECO_FORCE_OFFLINE=1 pytest tests/ -v

# NLU: 80/20 split, per-intent precision/recall/F1, confusion matrix
rasa test nlu --nlu data/nlu.yml --out docs/metrics/nlu

# NLU: 5-fold cross-validation (slower, more honest)
rasa test nlu --nlu data/nlu.yml --cross-validation --folds 5 --out docs/metrics/nlu-cv

# Dialogue: end-to-end conversation tests (needs the action server running)
rasa run actions --actions actions.actions &
rasa test core --stories tests/test_stories.yml --e2e --out docs/metrics/core

# Frontend
cd frontend && npm run typecheck && npm run build
```

Results land in `docs/metrics/`; `RESULTS.md` there is generated from the raw output by
`scripts/summarise_metrics.py`. `docs/evaluation.md` reads those numbers.

### Measured results

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

### Reproducing the transcripts

```bash
scripts/serve.sh start
python scripts/run_demo_conversations.py --out docs/transcripts
```

Seven scenarios covering the happy path, a strict long-distance profile, transparency
challenges, error recovery, input rejection, location sharing and mid-form escalation.
Each writes a Markdown transcript with per-turn latency, plus a JSON dump of every payload.

---

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

### Why the pipeline looks like this

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

## Deployment

### Hugging Face Spaces (zero cost)

```bash
rasa train --fixed-model-name eco_travel_advisor
cp deploy/huggingface/Dockerfile ./Dockerfile
# push to a Space with SDK = Docker, hardware = CPU basic
```

nginx serves the built client on port 7860 and proxies `/rasa` to the Rasa server in the
same container; the action server runs alongside on 5055 and is never exposed. API keys go
in the Space's **secrets**, not its variables.

### Security posture

The action server holds every credential and publishes no port in `docker-compose.yml`.
The browser never calls Rasa cross-origin — nginx proxies it — so the bot needs no
permissive CORS policy in production. The action container runs as an unprivileged user.
`.env` is git-ignored.

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

## Licence and attribution

Submitted as coursework. Emission factors are UK DESNZ/DEFRA open data; the gazetteer
derives from OpenStreetMap (ODbL). Hotel and experience datasets are synthetic and are
labelled as such in the files themselves and in the interface.
