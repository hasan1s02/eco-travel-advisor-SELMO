# Evaluation

Raw output is in `docs/metrics/`; `RESULTS.md` there is generated from it. This document
is the reading of those numbers — what was measured, what changed between iterations, and
what the remaining ceiling is caused by.

---

## Headline figures

| Measure | Result | Method |
|---|---|---|
| Intent classification | **0.775** accuracy, 0.772 weighted F1 | 5-fold cross-validation, 868 examples, 21 intents |
| Intent classification | **0.782** accuracy, 0.778 weighted F1 | 80/20 holdout, seed 42, 174 held-out examples |
| Entity extraction | **0.982** accuracy, 0.756 precision | 5-fold cross-validation |
| Dialogue — conversations | **14 / 14** (1.000) | End-to-end test stories, real NLU in the loop |
| Dialogue — action turns | **75 / 75** (1.000) | Same run |
| Unit tests | **60 / 60** | pytest, offline mode forced |
| Response latency | median **70 ms**, p95 **108 ms**, max **178 ms** | 49 live turns through the REST channel |

The two independent NLU estimates agreeing to within 0.007 is the useful part: cross-
validation and a seeded holdout are measuring the same thing and getting the same answer,
so 0.78 is the model's real generalisation performance rather than an artefact of one split.

The gap between training accuracy (0.999) and held-out accuracy (0.78) is large. The model
fits its training data essentially perfectly, so the limit is data coverage and intent
separability, not capacity — more epochs or a bigger encoder will not move it.

---

## Latency against the non-functional requirement

Section 2 of the brief sets a three-second ceiling for critical interactions. Measured over
49 live turns spanning all seven demonstration scenarios:

| | Value |
|---|---|
| Median | 70 ms |
| p95 | 108 ms |
| Max | 178 ms |
| Requirement | 3000 ms |

Comfortable, but the margin is a property of the configuration rather than of the design.
The measured runs use the bundled datasets. With live Climatiq calls the worst case is one
HTTP round trip per transport mode — up to eight on a long-distance route — which is why
`HTTP_TIMEOUT_SECONDS` is 2.0 and estimates are cached for 24 hours. A cold cache with
Climatiq responding slowly is the configuration that would threaten the budget, and it is
the one worth load-testing before any real deployment.

---

## Two measured iterations

The NLU was evaluated, diagnosed and rebuilt twice. Both rounds are reported because the
second one is the more interesting result.

### Round 1 — 0.668

386 examples across 21 intents. Error analysis showed the problem was not volume but
overlapping intent *definitions*: `inform` and `change_preference` were mutually confused
because change_preference examples were often bare values; `goodbye` and `affirm` collided
on "ok I'll go now"; `ask_carbon_footprint` contained both emissions questions and
"summarise everything". `out_of_scope` scored 0.08 F1 on 20 examples.

### Round 2 — 0.778

Examples roughly doubled to 786, and — more importantly — explicit boundary rules were
written into the top of `data/nlu.yml` and applied to every example: `change_preference`
must contain a change verb *and* name a field; `stop` must ask to halt, `deny` must refuse;
`goodbye` and `thanks` are never combined. A cross-intent duplicate check was added.

Accuracy went from 0.668 to 0.778, and `out_of_scope` from 0.08 to 0.49.

### Round 3 — 0.775

A third pass targeted the specific confusion pairs from round 2: the mutual
`ask_data_privacy` ↔ `ask_methodology` leak, shared phrasing between `deny` and `stop`, and
the open-ended `out_of_scope` class. 82 examples were added and eight ambiguous ones were
removed.

**Accuracy did not move.** 0.778 → 0.775, inside the fold-to-fold standard deviation of
0.030. The per-intent picture shows why:

| Intent | Round 2 F1 | Round 3 F1 | |
|---|---|---|---|
| `out_of_scope` | 0.49 | 0.59 | improved |
| `ask_data_privacy` | 0.56 | 0.72 | improved |
| `ask_methodology` | 0.66 | 0.78 | improved |
| `stop` | 0.65 | 0.81 | improved |
| `change_preference` | 0.77 | 0.83 | improved |
| `plan_trip` | 0.93 | 0.80 | regressed |
| `ask_carbon_footprint` | 0.80 | 0.69 | regressed |
| `restart_planning` | 0.82 | 0.65 | regressed |
| `goodbye` | 0.68 | 0.61 | regressed |

Every targeted intent improved, and the improvement was paid for elsewhere. This is what a
probability-mass ceiling looks like: with a fixed encoder and 21 classes that genuinely
overlap in short utterances, sharpening one boundary blurs its neighbours. Reporting the
plateau is more useful than reporting the best of three runs.

### What the remaining errors actually are

Of 195 cross-validation errors, the largest groups:

| True intent | Predicted as | Count | Is it wrong? |
|---|---|---|---|
| `out_of_scope` | `ask_data_privacy` | 12 | Partly. "Tell me about your training data" is both. |
| `restart_planning` | `plan_trip` | 5 | Barely. "New trip please" reasonably means either. |
| `ask_methodology` | `ask_carbon_footprint` | 5 | Behaviourally harmless — both explain figures. |
| `stop` | `deny` | 4 | Genuine confusion, and genuinely subtle. |

Two structural causes:

**`out_of_scope` is an open class.** 88 maximally diverse examples that share no features
with each other, asked to form one decision region. It both leaks into everything and
absorbs probability mass from everything. This is inherent to catch-all classes, not a data
problem with a data solution.

**Short social utterances carry little signal.** `affirm`, `deny`, `goodbye`, `thanks` and
`stop` are one to three words. "Leave it", "no need", "that's me done" are separable by
dialogue context, which DIET does not see — it classifies the utterance alone. A
context-aware classifier would help here; a bigger one would not.

**Behavioural impact is smaller than the number suggests.** Several frequent confusions map
to the same action: `ask_methodology` → `ask_carbon_footprint` both explain figures,
`restart_planning` → `plan_trip` both start intake. The end-to-end conversation tests —
which run real NLU against unseen phrasings — pass 14/14, because the dialogue layer is
tolerant of exactly the confusions the classifier makes.

---

## Entity extraction

| | Cross-validation | 80/20 holdout |
|---|---|---|
| Accuracy | 0.982 | — |
| Weighted F1 | — | 0.588 |
| Precision | 0.756 | — |

The holdout entity figure is much worse than cross-validation, and the reason is sample
size: the held-out 20% contains only 35 annotated entities in total, so a handful of misses
dominates. `travel_date.departure` scores 0.00 on nine instances there while
`city.destination` and `budget` score 1.00 on seven and four. Cross-validation, which sees
every example once, is the figure to trust.

The role split is the interesting part. DIET learns `city.origin` and `city.destination` as
distinct classes and gets them mostly right, which is what makes "from Berlin to Lisbon"
work in a single turn. Role assignment is weakest **inside the form**, where cues like
"setting off from" appear less often — the model extracts `city` with no role at all.

That failure was anticipated and is handled architecturally rather than by more training:
every intake slot has a second `from_entity` mapping conditioned on `requested_slot`, so
when the form has just asked "where are you starting from?", a bare `city` fills `origin`
regardless of role. The end-to-end test story annotates the role-less extraction rather than
the ideal one, so the test documents what the model does instead of what we wish it did.

---

## Dialogue management

14/14 conversations and 75/75 action turns, with real NLU in the loop and test utterances
that do not appear in the training data.

Getting there required fixing four defects that only end-to-end testing exposed.

**Infinite fallback loop.** A custom action wired as `core_fallback_action_name` is
re-predicted from the same unchanged state on the next step. Rasa appends `action_listen`
automatically only after the built-in `action_default_fallback`. The tracker showed
`action_two_stage_clarification` at RulePolicy confidence 0.4 repeating until the circuit
breaker tripped. Fixed by terminating every branch with `FollowupAction("action_listen")`,
and by running the escalation inline rather than chaining to another custom action, which
would reproduce the loop one level down.

**Featurized slots broke story matching.** With `influence_conversation: true` on the intake
slots, the runtime state diverged from every training story the moment the form filled them.
MemoizationPolicy stopped matching and the core fallback fired on messages the NLU had
classified at 1.000 confidence — a correctly understood "where should I stay?" produced a
clarification prompt. No slot is featurized now; branching is driven by the form's own
`requested_slot` mechanism.

**Button payloads were silently broken.** Rasa runs response text *and* button payloads
through a format-style interpolator. A payload of `/inform{"city": "Lisbon"}` is read as a
format field and raises `KeyError`, so the button shipped empty and did nothing. Seventeen
payloads needed their braces doubled. This is the kind of defect that survives code review
and dies in the first end-to-end test.

**`UnexpecTEDIntentPolicy` fired on ordinary form turns.** A form's slot-filling turns are
handled by the form and so never appear in training stories — exactly the evidence the
policy looks for. It emitted `action_unlikely_intent` on every intake turn, and the inserted
action changed the state enough to drop the next prediction below the fallback threshold.
Removed; `config.yml` records why.

---

## Unit tests

60 cases, all passing, over the deterministic layer: date parsing, geocoding, emission
estimates, API fallback behaviour, the scoring function and PII redaction.

Four of them caught real defects during development:

- **`Settings` was a frozen dataclass**, which made the live-API paths untestable without
  setting real environment variables.
- **The geocoder's prefix stripper was a fixed list** and failed on "I'm coming from
  Hamburg". Replaced with a stopword-run stripper.
- **Min–max normalisation amplified trivial differences.** `test_flexible_profile_can_prefer_a_cheaper_dirtier_option`
  failed because a nine-hour train beat a ten-hour coach on journey time as decisively as a
  one-hour flight beats a two-day drive. Fixed with relative-spread damping.
- **The budget penalty was a score multiplier**, so an unaffordable option could still rank
  first. `test_options_over_budget_are_demoted_not_hidden` failed. Affordability is now a
  hard constraint in the sort key, and the option stays visible.

The last two changed what the product recommends, not just whether the code runs.

---

## A calibration finding

`FallbackClassifier` is configured at threshold 0.60. In practice it almost never fires,
because DIET with `constrain_similarities: true` is badly calibrated on out-of-distribution
input. Measured directly against the trained model:

| Input | Predicted intent | Confidence |
|---|---|---|
| `mmmmm nnnn` | `greet` | 1.000 |
| `qwtx blorp zzz` | `inform` | 1.000 |
| `flurb glorp` | `inform` | 1.000 |
| `zzzz xkcd qqq` | `out_of_scope` | 0.935 |

Pure keyboard mash classified as a greeting at 1.000 confidence. No threshold can catch
that, so a confidence threshold cannot be the error-recovery mechanism for this
architecture — a conclusion that generalises past this assistant.

The design response was three independent routes rather than one: nonsense is trained
explicitly as `out_of_scope` so it reaches a response that offers a human; the RulePolicy
core fallback catches unmodelled dialogue states; and the `FallbackClassifier` threshold
remains as a third net for the genuinely ambiguous cases where it does still work.

---

## Limitations of this evaluation

- **No human participants yet.** `docs/user-testing-protocol.md` is written and ready but
  unrun. Every usability claim in this project is therefore a designer's assertion, not a
  finding. That is the single largest gap.
- **One evaluator, one machine.** Latency was measured on a 2-core container with a warm
  cache and no concurrency. It says nothing about behaviour under load.
- **The test conversations are scripted.** They use phrasings absent from training, but they
  were written by the person who wrote the training data, which is a narrower distribution
  than real travellers produce.
- **Offline data throughout.** Every measurement used the bundled datasets. The live-API
  paths are unit-tested with mocked responses but were never exercised against the real
  Climatiq or Amadeus services.
- **English only**, and a 78-city European gazetteer.
