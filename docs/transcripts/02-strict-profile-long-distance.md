# Scenario: 02 strict profile long distance

**Traveller:** plan a trip from Berlin to Lisbon

**Advisor:** When do you want to leave? A date like 12 May 2027, or something like "in three weeks", both work.

<sub>round trip 77 ms</sub>

**Traveller:** Berlin

**Advisor:** I couldn't read that as a date. Try something like "12 May 2027", "next Friday" or "in three weeks".

**Advisor:** When do you want to leave? A date like 12 May 2027, or something like "in three weeks", both work.

<sub>round trip 68 ms</sub>

**Traveller:** 3 June 2027

**Advisor:** And when are you coming back?

<sub>round trip 68 ms</sub>

**Traveller:** 14 June 2027

**Advisor:** Roughly what's your total budget for the trip, per person, in euros?

> Quick replies: `Under €300` · `€300-700` · `€700+`

<sub>round trip 65 ms</sub>

**Traveller:** just me

**Advisor:** Roughly how much per person, in euros? A ballpark figure is enough — "about 500" works.

**Advisor:** Roughly what's your total budget for the trip, per person, in euros?

> Quick replies: `Under €300` · `€300-700` · `€700+`

<sub>round trip 68 ms</sub>

**Traveller:** 1200

**Advisor:** Last one. How strictly do you want me to weight environmental impact against cost and travel time?

> Quick replies: `Strict — lowest emissions wins` · `Balanced — trade off sensibly` · `Flexible — cost and time matter more`

<sub>round trip 68 ms</sub>

**Traveller:** strict, lowest emissions

**Advisor:** You've asked for the strictest profile, so one extra question: should I also show carbon offset or contribution schemes for whatever emissions remain?

I'll be straight with you — offsetting does not undo a flight, and the evidence on many offset projects is contested. Reducing emissions first is the part that reliably works.

> Quick replies: `Yes, show me offsets` · `No, reductions only`

<sub>round trip 77 ms</sub>

**Traveller:** yes, show me offsets

**Advisor:** I don't have your route yet, so this uses a placeholder of 250 kg CO₂e per traveller. Plan the trip first and I'll price it against your real figure.

**Advisor:** Before offsets: offsetting does not undo a journey, and the evidence behind many credits is weak. Shifting one return short-haul flight to rail typically saves more CO2e than a year of average household recycling.

**[offset options]** for 250 kg CO₂e

- Improved cookstove programme (Gold Standard) — €4.50, medium confidence
- Native woodland restoration (Verra VCS) — €6.00, low confidence
- Biochar carbon removal (Puro.earth) — €33.75, high confidence
- Enhanced rock weathering (EU Carbon Removals Certification Framework (pilot)) — €52.50, medium confidence
- Direct air capture with geological storage (Puro.earth / ISO 14064-2) — €95.00, high confidence

<sub>round trip 111 ms</sub>

**Traveller:** how did you calculate that?

**Advisor:** Here's exactly how the numbers are produced.

**Advisor:** **Emissions.** Distance × a published emission factor per passenger-kilometre. Factors come from UK DESNZ/DEFRA Greenhouse Gas Reporting: Conversion Factors 2023, business travel tables, bundled offline in this build. Straight-line distance is multiplied by a route-circuity factor (1.20 rail, 1.25 road, 1.05 air plus a 40 km routing allowance), because trains and roads don't travel in straight lines.

**Advisor:** **Ranking.** A weighted sum of three min-max normalised criteria. On your **strict** profile that's emissions 65%, cost 15%, journey time 20%. Options over your budget are demoted rather than hidden.

**Advisor:** **Accommodation.** Ranked on certification credibility (audited against a GSTC-recognised standard beats audited, which beats self-declared), renewable electricity share, walking distance to transit, local sourcing and price.

**Advisor:** **And what these numbers are not.**

They're fleet averages, not measurements of your specific journey — load factor, aircraft type and electricity mix all move the real figure. Accommodation emissions use a flat 12 kg per person per night, which is a rough European hotel average and nothing more. Availability, prices and certifications in this build come from a bundled demonstration dataset, so treat them as illustrative rather than bookable.

If a number matters to a real decision, check it against the operator's own reporting.

> Quick replies: `Carry on planning` · `Talk to a human advisor`

**Advisor:** You've asked for the strictest profile, so one extra question: should I also show carbon offset or contribution schemes for whatever emissions remain?

I'll be straight with you — offsetting does not undo a flight, and the evidence on many offset projects is contested. Reducing emissions first is the part that reliably works.

> Quick replies: `Yes, show me offsets` · `No, reductions only`

<sub>round trip 108 ms</sub>

---
Latency: median 68 ms · p95 108 ms · max 111 ms