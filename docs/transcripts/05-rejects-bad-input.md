# Scenario: 05 rejects bad input

**Traveller:** I want to plan a trip

**Advisor:** Where would you like to travel to?

> Quick replies: `Lisbon` · `Copenhagen` · `Ljubljana` · `Somewhere else`

<sub>round trip 68 ms</sub>

**Traveller:** Atlantis

**Advisor:** I couldn't find "Atlantis". I cover European cities — try the city name on its own, for example "Lisbon" or "Ljubljana".

> Quick replies: `Lisbon` · `Copenhagen` · `Talk to a human`

**Advisor:** Where would you like to travel to?

> Quick replies: `Lisbon` · `Copenhagen` · `Ljubljana` · `Somewhere else`

<sub>round trip 73 ms</sub>

**Traveller:** Lisbon

**Advisor:** And where are you starting from? You can share your location instead if that's easier.

> Quick replies: `Use my location`

<sub>round trip 77 ms</sub>

**Traveller:** Lisbon

**Advisor:** That's the same as your destination. Where are you actually setting off from?

**Advisor:** And where are you starting from? You can share your location instead if that's easier.

> Quick replies: `Use my location`

<sub>round trip 63 ms</sub>

**Traveller:** Berlin

**Advisor:** When do you want to leave? A date like 12 May 2027, or something like "in three weeks", both work.

<sub>round trip 64 ms</sub>

**Traveller:** banana

**Advisor:** I couldn't read that as a date. Try something like "12 May 2027", "next Friday" or "in three weeks".

**Advisor:** When do you want to leave? A date like 12 May 2027, or something like "in three weeks", both work.

<sub>round trip 68 ms</sub>

**Traveller:** 12 May 2027

**Advisor:** And when are you coming back?

<sub>round trip 70 ms</sub>

**Traveller:** 1 January 2020

**Advisor:** 1 January 2020 has already passed. When would you like to leave?

**Advisor:** When do you want to leave? A date like 12 May 2027, or something like "in three weeks", both work.

<sub>round trip 74 ms</sub>

**Traveller:** 19 May 2027

**Advisor:** Roughly what's your total budget for the trip, per person, in euros?

> Quick replies: `Under €300` · `€300-700` · `€700+`

<sub>round trip 72 ms</sub>

**Traveller:** fifty people

**Advisor:** How many people are travelling in total? A number is fine.

**Advisor:** Roughly how much per person, in euros? A ballpark figure is enough — "about 500" works.

**Advisor:** How many people are travelling?

> Quick replies: `Just me` · `2` · `3-4`

<sub>round trip 75 ms</sub>

**Traveller:** 2

**Advisor:** Roughly what's your total budget for the trip, per person, in euros?

> Quick replies: `Under €300` · `€300-700` · `€700+`

<sub>round trip 74 ms</sub>

**Traveller:** 500

**Advisor:** Last one. How strictly do you want me to weight environmental impact against cost and travel time?

> Quick replies: `Strict — lowest emissions wins` · `Balanced — trade off sensibly` · `Flexible — cost and time matter more`

<sub>round trip 77 ms</sub>

**Traveller:** strict

**Advisor:** You've asked for the strictest profile, so one extra question: should I also show carbon offset or contribution schemes for whatever emissions remain?

I'll be straight with you — offsetting does not undo a flight, and the evidence on many offset projects is contested. Reducing emissions first is the part that reliably works.

> Quick replies: `Yes, show me offsets` · `No, reductions only`

<sub>round trip 76 ms</sub>

**Traveller:** no

**Advisor:** Got it. Working out your options now — one moment.

**Advisor:** Berlin to Lisbon is about 2312 km in a straight line. Here's how the options compare for 2 travellers, weighted for a **strict** profile.

**[transport comparison card]**

| Mode | CO₂e/person | Cost | Time | Band |
|---|---|---|---|---|
| High-speed rail | 39 kg | €444 | 16 h | moderate |
| Night train (sleeper) | 68 kg | €210 | 40 h | moderate |
| Long-distance coach | 78 kg | €173 | 45 h | moderate |
| Electric car (EU grid) | 137 kg | €260 | 34 h | high |
| Petrol car (2 people) | 247 kg | €101 | 34 h | high |
| Short-haul flight | 373 kg | €321 | 7 h | high |
| Petrol car (1 person) | 494 kg | €405 | 34 h | high |

_Figures from the bundled demonstration dataset — illustrative, not live._

**Advisor:** **High-speed rail** comes out on top: about **39 kg CO₂e** per person, €444, roughly 16 hours door to door. That's 455 kg less per person than petrol car (1 person) — 911 kg across your group.

**[warning alert]** High-emission options in this list — Electric car (EU grid), Petrol car (2 people), Short-haul flight exceed 120 kg CO₂e per person for this journey.

**Advisor:** What would you like to look at next?

> Quick replies: `Places to stay` · `Things to do` · `Full summary` · `Talk to a human advisor`

<sub>round trip 178 ms</sub>

---
Latency: median 74 ms · p95 77 ms · max 178 ms