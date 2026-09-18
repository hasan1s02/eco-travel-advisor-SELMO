# System architecture

```mermaid
flowchart TB
    subgraph browser["Browser"]
        UI["React 18 + TypeScript<br/>Vite build, nginx-served"]
        GEO["Geolocation API<br/>rounded to 2 dp before sending"]
        SPEECH["Web Speech API<br/>progressive enhancement"]
    end

    subgraph edge["nginx :3000 / :7860"]
        STATIC["Static assets"]
        PROXY["/rasa → rasa:5005<br/>same-origin, so no CORS policy needed"]
    end

    subgraph rasa["Rasa server :5005"]
        REST["REST channel"]
        NLU["NLU pipeline<br/>SpacyNLP → SpacyTokenizer → SpacyFeaturizer<br/>RegexFeaturizer → CountVectors ×2 → DIET<br/>→ EntitySynonymMapper → FallbackClassifier"]
        CORE["Dialogue policies<br/>Memoization → Rule → TED"]
        TRACKER[("Tracker store<br/>in-memory, 60 min expiry")]
    end

    subgraph actions["Action server :5055 — holds every credential, no published port"]
        ACT["actions.py<br/>13 custom actions + form validation"]
        SCORE["eco_scoring.py<br/>weighted MCDA + spread damping"]
        GEOM["geo.py<br/>geocode · reverse · route distance"]
        DATES["date_utils.py<br/>dependency-free NL dates"]
        HAND["handover.py<br/>payload · redaction · delivery"]
        CLIENTS["api_clients.py<br/>adapters + TTL cache + fallbacks"]
    end

    subgraph external["External services — all optional"]
        CLIM["Climatiq<br/>500 calls/month"]
        AMA["Amadeus sandbox<br/>free tier"]
        OC["OpenCage<br/>2,500/day"]
        ORS["OpenRouteService<br/>2,000/day"]
    end

    subgraph offline["Bundled datasets — the fallback for every one of them"]
        F1["transport_factors.json<br/>DESNZ/DEFRA 2023"]
        F2["city_gazetteer.json<br/>78 cities, OSM"]
        F3["eco_hotels.json<br/>synthetic, labelled"]
        F4["experiences.json"]
        F5["carbon_offsets.json"]
    end

    UI --> STATIC
    UI -->|"POST /webhooks/rest/webhook"| PROXY
    GEO -.->|"metadata.location"| UI
    SPEECH -.-> UI
    PROXY --> REST
    REST --> NLU --> CORE --> TRACKER
    CORE -->|"action_endpoint"| ACT
    ACT --> SCORE & GEOM & DATES & HAND & CLIENTS
    CLIENTS -->|"if key set"| CLIM & AMA
    GEOM -->|"if key set"| OC & ORS
    CLIENTS -->|"always available"| F1 & F3 & F4 & F5
    GEOM --> F2
    CLIM -.->|"timeout · 5xx · quota"| F1
    AMA -.->|"timeout · 5xx · no offers"| F3
    OC -.->|"timeout · not found"| F2

    classDef fallback fill:#fdf1dc,stroke:#c9871a,color:#7a4a05
    classDef secure fill:#fce8e6,stroke:#c4342a,color:#8a1c13
    class F1,F2,F3,F4,F5 fallback
    class actions secure
```

## Request path for one message

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant N as nginx
    participant R as Rasa
    participant A as Action server
    participant X as Climatiq

    B->>N: POST /rasa/webhooks/rest/webhook
    N->>R: proxied, same origin
    R->>R: DIET → intent + entities with roles
    R->>R: policies → next action
    R->>A: POST /webhook {tracker, domain}

    A->>A: geocode both ends (cache, then gazetteer)
    A->>A: available_modes(distance) — filter the physically absurd

    loop per transport mode
        A->>X: POST /data/v1/estimate
        alt 200 within 2 s
            X-->>A: co2e
        else timeout, 5xx or no key
            Note over A: fall back to the bundled factor,<br/>mark result degraded
        end
    end

    A->>A: score_transport_options(level, budget)
    A-->>R: [text, json_message, buttons]
    R-->>N: JSON array
    N-->>B: rendered as colour-coded cards
```

The loop is why `HTTP_TIMEOUT_SECONDS` defaults to 2.0 and why estimates are cached for 24
hours: a long-distance route offers up to eight modes, and eight sequential two-second
worst cases would blow the three-second response requirement several times over. In
practice the cache is warm after the first comparison of a given route, and a cold miss with
Climatiq down costs one timeout per mode before the offline factor answers instantly.

## Deployment topologies

| | Development | Docker Compose | Hugging Face Spaces |
|---|---|---|---|
| Frontend | Vite dev server :3000 | nginx :3000 | nginx :7860 |
| Rasa | :5005 | internal, bound to 127.0.0.1 | internal :5005 |
| Actions | :5055 | internal, **no published port** | internal :5055 |
| Process manager | three terminals | Compose | supervisord, one container |
| Secrets | `.env` | Compose environment | Space secrets |

The action server is the process that holds every API key and makes every outbound call. It
publishes no port in any of the three topologies; only Rasa can reach it, and only over the
internal network.
