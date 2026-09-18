# Conversation flows and interaction design

Mermaid diagrams render directly on GitHub, so these stay in version control with the code
they describe rather than drifting in a separate design tool. Screenshot them for the
report if you need images.

---

## 1. Top-level dialogue architecture

```mermaid
flowchart TD
    START([Traveller opens the assistant]) --> GREET[utter_greet<br/>+ quick replies]

    GREET --> ROUTE{Intent}

    ROUTE -->|plan_trip| FORM[trip_form<br/>adaptive intake]
    ROUTE -->|ask_methodology| METHOD[action_explain_methodology]
    ROUTE -->|ask_data_privacy| PRIV[action_explain_privacy]
    ROUTE -->|request_human_agent| HAND[action_handover_to_human]
    ROUTE -->|out_of_scope| OOS[utter_out_of_scope]
    ROUTE -->|nlu_fallback| CLAR[action_two_stage_clarification]

    FORM --> RESOLVE[action_resolve_locations<br/>geocode + distance]
    RESOLVE --> COMPARE[action_compare_transport<br/>estimate + rank]
    COMPARE --> MENU[utter_ask_continue_planning]

    MENU -->|ask_eco_hotels| HOTELS[action_recommend_hotels]
    MENU -->|ask_cultural_experiences| EXP[action_recommend_experiences]
    MENU -->|ask_carbon_offset| OFF[action_recommend_offsets]
    MENU -->|ask_carbon_footprint| SUM[action_trip_summary]
    MENU -->|request_human_agent| HAND

    HOTELS --> MENU
    EXP --> MENU
    OFF --> MENU
    SUM --> MENU

    METHOD -.resumes.-> MENU
    PRIV -.resumes.-> MENU
    OOS -->|affirm| HAND
    CLAR -->|3rd failure| HAND

    HAND --> END([Human advisor holds the conversation])

    classDef action fill:#e4f0e8,stroke:#1f6b45,color:#14532d
    classDef escalate fill:#fdf1dc,stroke:#c9871a,color:#7a4a05
    class FORM,RESOLVE,COMPARE,HOTELS,EXP,OFF,SUM,METHOD,PRIV action
    class HAND,CLAR escalate
```

Two things this diagram is meant to make obvious. First, `request_human_agent` is reachable
from every state, including mid-form — it is a rule, not a story, so no policy can decline
it. Second, transparency (`ask_methodology`, `ask_data_privacy`) is also reachable from
everywhere and returns the traveller to exactly where they were. An assistant that can only
justify itself at the end is not auditable during the decision.

---

## 2. Adaptive intake

```mermaid
flowchart TD
    A[trip_form activates] --> B[destination]
    B --> V1{geocodes?}
    V1 -->|no| B2[Re-prompt with<br/>example cities + human option]
    B2 --> B
    V1 -->|yes| C[origin]

    C --> GPS{Shared location<br/>in metadata?}
    GPS -->|yes| RG[reverse_geocode<br/>2 dp ≈ 1 km]
    RG --> D
    GPS -->|no| V2{geocodes?<br/>differs from destination?}
    V2 -->|no| C
    V2 -->|yes| D[departure_date]

    D --> V3{parses?<br/>in the future?}
    V3 -->|no| D
    V3 -->|yes| E[return_date]

    E --> V4{parses?<br/>after departure?<br/>≤ 90 nights?}
    V4 -->|over 90 nights| ESC[Offer a human advisor]
    V4 -->|no| E
    V4 -->|yes| F[travellers]

    F --> V5{1 to 12?}
    V5 -->|over 12| ESC
    V5 -->|no| F
    V5 -->|yes| G[budget]

    G --> H[sustainability_level]
    H --> ADAPT{level == strict?}
    ADAPT -->|yes| I[offset_interest<br/>*only asked here*]
    ADAPT -->|no| DONE
    I --> DONE([Form complete])

    classDef adapt fill:#e4f0e8,stroke:#1f6b45,color:#14532d
    class I,ADAPT adapt
```

`offset_interest` is declared in the domain so Rasa can validate its mapping conditions, but
`ValidateTripForm.required_slots` **removes** it unless the traveller chose the strict
profile. Everyone else never sees the question. That is the adaptive-questioning mechanism:
the form's shape is a function of the answers already given, not a fixed script.

Every validator that rejects an answer re-prompts with a worked example, and the two that
detect a request outside the assistant's competence — a trip over 90 nights, a group over
twelve — offer a human immediately instead of continuing to collect data it cannot use.

---

## 3. Error recovery: two stages, then escalate

```mermaid
sequenceDiagram
    autonumber
    participant T as Traveller
    participant N as FallbackClassifier
    participant A as action_two_stage_clarification
    participant H as action_handover_to_human

    T->>N: ambiguous message
    N->>A: nlu_fallback (conf < 0.60 or gap < 0.12)
    Note over A: clarification_stage 0 → 1
    A->>T: "I'm not sure what you meant by '…'. Could you put it another way?"

    T->>N: still ambiguous
    N->>A: nlu_fallback
    Note over A: stage 1 → 2
    A->>T: Constrained quick replies:<br/>plan · transport · stay · do · get a human

    T->>N: still ambiguous
    N->>A: nlu_fallback
    Note over A: stage ≥ 2 — stop asking
    A->>T: "I've asked twice and I'm still not following —<br/>that's my limit, not yours."
    A->>H: FollowupAction
    H->>T: Handover card + reference + full brief
```

The escalation on the third failure is issued as a `FollowupAction` from inside the action,
not predicted by a policy. That is deliberate: modelling it as a story would contradict the
`nlu_fallback` rule, which correctly predicts `action_listen` after every clarification
turn. `tests/test_stories.yml` covers the behaviour instead.

The design choice underneath: a bot that re-prompts indefinitely is worse than one that
admits defeat. Two attempts, then a person.

---

## 4. Human handover payload

```mermaid
flowchart LR
    TRIG[Escalation triggered] --> BUILD[handover.build_payload]

    BUILD --> S[Trip brief<br/>route · dates · group · budget · priority]
    BUILD --> R[Recommendations already shown<br/>top 5 transport, top 5 hotels]
    BUILD --> U[Unresolved fields<br/>what intake never captured]
    BUILD --> N[Advisor notes<br/>where the bot hit its limits]
    BUILD --> TR[Transcript, last 40 turns<br/>with intents and confidences]

    TR --> RED[handover.redact]
    RED -->|strips| PII[emails · phones<br/>card-length digits · passport patterns]

    S & R & U & N & RED --> P[(Payload + ETA-XXXXXXXX reference)]

    P --> W{Webhook configured<br/>and reachable?}
    W -->|yes| POST[POST to advisor desk]
    W -->|no| Q[Append to local JSONL queue]

    POST --> OK[Card: delivered]
    Q --> OK2[Card: queued, brief shown<br/>so the traveller can forward it]

    classDef privacy fill:#fce8e6,stroke:#c4342a,color:#8a1c13
    class RED,PII privacy
```

The advisor notes are the part that matters in practice. They say *why* the bot gave up —
"intake incomplete, still missing origin", "traveller asked for the strictest profile but
the best option is still a flight", "no option came in under the stated budget" — so the
advisor starts from the bot's reasoning rather than from a raw transcript.

Nothing is ever lost: if the webhook is down the payload lands in a local queue and the
traveller is shown their brief so they can forward it themselves.

---

## 5. Interface elements

Mapped to the concrete UI requirements in section 3 of the brief.

| Requirement | Implementation | File |
|---|---|---|
| Quick-reply buttons for destination and preference selection | `buttons` on Rasa responses, rendered as pill buttons; disabled while a request is in flight | `App.tsx` |
| Carousels displaying eco-friendly hotels | Horizontal scroll-snap region, keyboard-reachable, `role="group"` with a described scroll axis | `Cards.tsx` |
| Colour-coded result cards (green / amber / red) | `band` on every option drives a left border, badge and bar | `Cards.tsx`, `styles.css` |
| Alert messages highlighting high-emission options | `type: "alert"` payload, `role="alert"` for warnings | `Cards.tsx` |
| Clear indications of human handover | Handover card **and** a persistent banner that stays visible after the message scrolls away | `App.tsx` |
| Location input via GPS or typing | "Use my location" quick reply; coordinates rounded in the browser before sending | `rasa.ts` |
| Alternative interaction modes (optional) | Web Speech API dictation, progressively enhanced — the button only appears where supported | `App.tsx` |

### Accessibility

Colour is never the only carrier of meaning. Every band shows a colour, a word
("Low emissions") and a glyph, which is what keeps the ranking readable for the roughly one
in twelve men with a colour-vision deficiency — a group large enough that a
sustainability tool relying on green-versus-red would fail a meaningful share of its users.

- Each transport option carries an `aria-label` that reads as one complete sentence, because
  a screen-reader user gets no help from column alignment or a bar chart.
- The transcript is a `role="log"` with `aria-live="polite"`: new messages are announced
  without stealing focus mid-typing.
- Every interactive target is at least 44 × 44 CSS px.
- Focus is always visible; a skip link jumps past the transcript to the message box.
- All animation is suppressed under `prefers-reduced-motion`.
- Both themes were checked for 4.5:1 body-text contrast, 3:1 for large numerals.

### Cognitive load

The intake asks one question per turn, with quick replies wherever the answer space is
closed. Recommendation cards lead with the single number that matters — kilograms of CO₂e —
and put cost, time and distance on a secondary line. Every card explains its own ranking in
one sentence, so the traveller never has to take "this is greenest" on trust.
