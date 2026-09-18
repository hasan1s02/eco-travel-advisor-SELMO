#!/usr/bin/env python3
"""Drive scripted conversations through the running bot and save transcripts.

Produces the evidence the report needs — real dialogue, real numbers, real
latencies — without hand-copying anything out of a chat window.

    # in separate terminals
    rasa run actions --actions actions.actions
    rasa run --enable-api --cors "*"

    python scripts/run_demo_conversations.py --out docs/transcripts

Writes one Markdown transcript per scenario plus a JSON dump of every payload,
and prints a latency summary against the three-second requirement.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import requests

DEFAULT_URL = "http://localhost:5005/webhooks/rest/webhook"

# Each scenario is a list of (what the user types, optional metadata).
SCENARIOS: dict[str, list[tuple[str, dict[str, Any] | None]]] = {
    "01-short-city-break": [
        ("hi there", None),
        ("I want to plan a low carbon city break", None),
        ("Copenhagen", None),
        ("I'm coming from Hamburg", None),
        ("12 May 2027", None),
        ("back on 16 May 2027", None),
        ("2", None),
        ("about 700 euros", None),
        ("balanced please", None),
        ("where should I stay?", None),
        ("what can I do there?", None),
        ("give me the full summary", None),
    ],
    "02-strict-profile-long-distance": [
        ("plan a trip from Berlin to Lisbon", None),
        ("Berlin", None),
        ("3 June 2027", None),
        ("14 June 2027", None),
        ("just me", None),
        ("1200", None),
        ("strict, lowest emissions", None),
        ("yes, show me offsets", None),
        ("how did you calculate that?", None),
    ],
    "03-transparency-and-scepticism": [
        ("hello", None),
        ("is carbon offsetting actually a scam?", None),
        ("where do your numbers come from?", None),
        ("what do you do with my data?", None),
    ],
    "04-error-recovery-and-escalation": [
        ("hi", None),
        ("qwtx blorp zzz", None),
        ("asdfgh jjjj", None),
        ("mmmmm nnnn", None),
    ],
    "05-rejects-bad-input": [
        ("I want to plan a trip", None),
        ("Atlantis", None),
        ("Lisbon", None),
        ("Lisbon", None),
        ("Berlin", None),
        ("banana", None),
        ("12 May 2027", None),
        ("1 January 2020", None),
        ("19 May 2027", None),
        ("fifty people", None),
        ("2", None),
        ("500", None),
        ("strict", None),
        ("no", None),
    ],
    "06-location-sharing": [
        ("plan a trip", None),
        ("Vienna", None),
        # Simulates the browser geolocation payload the React client sends.
        ("/share_location", {"location": {"latitude": 52.52, "longitude": 13.40}}),
    ],
    "07-mid-form-escalation": [
        ("help me plan a holiday", None),
        ("Porto", None),
        ("this is too fiddly, get me a human", None),
    ],
}


def send(url: str, sender: str, message: str, metadata: dict[str, Any] | None) -> tuple[list[dict], float]:
    started = time.perf_counter()
    response = requests.post(
        url,
        json={"sender": sender, "message": message, "metadata": metadata or {}},
        timeout=30,
    )
    elapsed = (time.perf_counter() - started) * 1000
    response.raise_for_status()
    return response.json(), elapsed


def render(payload: dict[str, Any]) -> str:
    """Summarise a custom payload the way the UI renders it."""
    kind = payload.get("type")

    if kind == "transport_options":
        rows = [
            f"| {o['label']} | {o['kg_co2e_per_traveller']:.0f} kg | €{o['cost_eur_per_traveller']:.0f} "
            f"| {o['duration_h']:.0f} h | {o['band']} |"
            for o in payload["options"]
        ]
        return (
            "**[transport comparison card]**\n\n"
            "| Mode | CO₂e/person | Cost | Time | Band |\n|---|---|---|---|---|\n"
            + "\n".join(rows)
            + f"\n\n_{payload['provenance']}_"
        )

    if kind == "hotel_carousel":
        rows = [
            f"| {h['name']} | {h.get('cert') or '—'} | €{h.get('price_eur') or 0:.0f} | {h['band']} |"
            for h in payload["hotels"]
        ]
        return (
            "**[accommodation carousel]**\n\n"
            "| Property | Certification | Per night | Band |\n|---|---|---|---|\n"
            + "\n".join(rows)
            + f"\n\n_{payload['provenance']}_"
        )

    if kind == "experience_list":
        def price(experience: dict[str, Any]) -> str:
            value = experience["price_eur"]
            return "free" if not value else f"€{value:.0f}"

        return "**[experience list]**\n\n" + "\n".join(
            f"- {e['name']} — {e['impact'].replace('_', ' ')} impact, {price(e)}, "
            f"{e['community_benefit']} local benefit"
            for e in payload["experiences"]
        )

    if kind == "offset_list":
        return "**[offset options]** for {:.0f} kg CO₂e\n\n".format(payload["residual_kg_co2e"]) + "\n".join(
            f"- {p['type']} ({p['standard']}) — €{p['estimated_cost_eur']:.2f}, {p['confidence']} confidence"
            for p in payload["providers"]
        )

    if kind == "trip_summary":
        f = payload["footprint"]
        return (
            f"**[trip summary card]** {payload['origin']} → {payload['destination']}\n\n"
            f"- Total: **{f['total_kg_per_traveller']:.0f} kg CO₂e per traveller** "
            f"({f['total_kg_group']:.0f} kg group), band `{f['band']}`\n"
            f"- Travel {f['journey_kg_per_traveller']:.0f} kg · stay {f['stay_kg_per_traveller']:.0f} kg\n"
            f"- Estimated cost €{payload['estimated_cost_eur_per_traveller']:.0f} per person"
        )

    if kind == "alert":
        return f"**[{payload['level']} alert]** {payload['title']} — {payload['body']}"

    if kind == "handover":
        return (
            f"**[handover card]** status `{payload['status']}` via `{payload['channel']}`, "
            f"reference **{payload['reference']}**\n\n"
            + "\n".join(f"- {note}" for note in payload["advisor_notes"])
        )

    return f"**[{kind}]**\n```json\n{json.dumps(payload, indent=2)[:600]}\n```"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--out", default="docs/transcripts")
    parser.add_argument("--only", help="run a single scenario by name")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    scenarios = {args.only: SCENARIOS[args.only]} if args.only else SCENARIOS
    all_latencies: list[float] = []
    raw_dump: dict[str, Any] = {}

    for name, turns in scenarios.items():
        sender = f"demo-{name}-{int(time.time())}"
        lines = [f"# Scenario: {name.replace('-', ' ')}", ""]
        scenario_raw: list[dict[str, Any]] = []
        latencies: list[float] = []

        print(f"\n▶ {name}")
        for message, metadata in turns:
            try:
                responses, elapsed = send(args.url, sender, message, metadata)
            except Exception as exc:
                print(f"  ✗ {message!r}: {exc}")
                lines.append(f"**Traveller:** {message}\n\n> Request failed: {exc}\n")
                continue

            latencies.append(elapsed)
            all_latencies.append(elapsed)
            scenario_raw.append({"user": message, "metadata": metadata, "responses": responses, "ms": round(elapsed)})

            lines.append(f"**Traveller:** {message}")
            lines.append("")
            for item in responses:
                if item.get("text"):
                    lines.append(f"**Advisor:** {item['text']}")
                    lines.append("")
                if item.get("buttons"):
                    chips = " · ".join(f"`{b['title']}`" for b in item["buttons"])
                    lines.append(f"> Quick replies: {chips}")
                    lines.append("")
                if item.get("custom"):
                    lines.append(render(item["custom"]))
                    lines.append("")
            lines.append(f"<sub>round trip {elapsed:.0f} ms</sub>")
            lines.append("")
            print(f"  ✓ {message[:44]:46} {elapsed:6.0f} ms  ({len(responses)} messages)")

        if latencies:
            lines.append("---")
            lines.append(
                f"Latency: median {statistics.median(latencies):.0f} ms · "
                f"p95 {sorted(latencies)[int(len(latencies) * 0.95) - 1]:.0f} ms · "
                f"max {max(latencies):.0f} ms"
            )

        (out_dir / f"{name}.md").write_text("\n".join(lines), encoding="utf-8")
        raw_dump[name] = scenario_raw

    (out_dir / "raw_responses.json").write_text(json.dumps(raw_dump, indent=2, ensure_ascii=False), encoding="utf-8")

    if all_latencies:
        ordered = sorted(all_latencies)
        p95 = ordered[max(int(len(ordered) * 0.95) - 1, 0)]
        print(
            f"\n{len(all_latencies)} turns · median {statistics.median(all_latencies):.0f} ms "
            f"· p95 {p95:.0f} ms · max {max(all_latencies):.0f} ms"
        )
        print(f"3000 ms requirement: {'PASS' if p95 < 3000 else 'FAIL'} at p95")
        print(f"Transcripts written to {out_dir}/")

    return 0


if __name__ == "__main__":
    sys.exit(main())
