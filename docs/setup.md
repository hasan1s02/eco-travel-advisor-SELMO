# Setup, testing and deployment

Detailed instructions behind the short version in the README.

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

### Reproducing the transcripts

```bash
scripts/serve.sh start
python scripts/run_demo_conversations.py --out docs/transcripts
```

Seven scenarios covering the happy path, a strict long-distance profile, transparency
challenges, error recovery, input rejection, location sharing and mid-form escalation.
Each writes a Markdown transcript with per-turn latency, plus a JSON dump of every payload.

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
