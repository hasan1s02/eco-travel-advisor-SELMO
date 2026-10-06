# Eco-Travel Advisor

A Rasa chatbot that helps travellers plan lower-carbon trips. It asks where, when and how the traveller wants to travel, compares transport options by emissions, cost and time, suggests certified accommodation and local activities, and hands the conversation to a human advisor when needed.

*MSc Artificial Intelligence · Advanced Conversational UI Design and Chatbot Development · BSBI*

**Live demo:** https://huggingface.co/spaces/hasanns1/eco-travel-SELMO

## Features

- Multi-turn trip intake (destination, origin or GPS, dates, group size, budget, sustainability priority)
- Emission estimates per transport mode (Climatiq, with UK DESNZ 2023 factors as fallback)
- Ranking weighted by the traveller's priority: strict, balanced or flexible
- Accommodation, activities and offsets; colour-coded cards and quick replies (React)
- Two-stage error recovery and human handover with a redacted trip summary

## Run it

Needs Docker only. The model is not stored in the repo, so it is trained once first (~15 min):

```bash
git clone https://github.com/hasan1s02/eco-travel-advisor-SELMO.git eco-travel-advisor
cd eco-travel-advisor
docker compose --profile train run --rm train
docker compose up --build
```

Then open http://localhost:3000. No API keys are required: without them the bot uses the bundled datasets and says so on every card. Running without Docker (Python 3.10), Windows steps and Hugging Face deployment are in [docs/setup.md](docs/setup.md).

## Tests and results

Unit tests: `ECO_FORCE_OFFLINE=1 pytest tests/` (84 passing). Dialogue tests: `rasa test core --stories tests/test_stories.yml --e2e` (14/14 conversations). Intent accuracy is 0.775 in 5-fold cross-validation; median response time is 70 ms. Two user-testing sessions found seven defects, all fixed ([docs/user-tests/](docs/user-tests/)).

## More detail

- [docs/design-notes.md](docs/design-notes.md): how the numbers are produced, pipeline choices, data protection, known limitations
- [docs/evaluation.md](docs/evaluation.md): NLU and dialogue evaluation
- [docs/architecture.md](docs/architecture.md) and [docs/conversation-flows.md](docs/conversation-flows.md): diagrams

Amadeus closed its free developer sandbox in July 2026, so hotel and flight data always come from the fallback datasets. Hotel and activity datasets are synthetic.
