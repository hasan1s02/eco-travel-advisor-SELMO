# Scenario: 03 transparency and scepticism

**Traveller:** hello

**Advisor:** Hi — I'm the Eco-Travel Advisor. I help you plan a trip with a much smaller carbon footprint: low-emission routes, certified accommodation and local experiences that keep money in the community.

I'll estimate emissions for each option and show you exactly how I got the number. Where would you like to go?

> Quick replies: `Plan a trip` · `Compare travel emissions` · `How do you calculate this?`

<sub>round trip 44 ms</sub>

**Traveller:** is carbon offsetting actually a scam?

**Advisor:** I don't have your route yet, so this uses a placeholder of 250 kg CO₂e per traveller. Plan the trip first and I'll price it against your real figure.

**Advisor:** Before offsets: offsetting does not undo a journey, and the evidence behind many credits is weak. Shifting one return short-haul flight to rail typically saves more CO2e than a year of average household recycling.

**[offset options]** for 250 kg CO₂e

- Improved cookstove programme (Gold Standard) — €4.50, medium confidence
- Native woodland restoration (Verra VCS) — €6.00, low confidence
- Biochar carbon removal (Puro.earth) — €33.75, high confidence
- Enhanced rock weathering (EU Carbon Removals Certification Framework (pilot)) — €52.50, medium confidence
- Direct air capture with geological storage (Puro.earth / ISO 14064-2) — €95.00, high confidence

<sub>round trip 78 ms</sub>

**Traveller:** where do your numbers come from?

**Advisor:** Here's exactly how the numbers are produced.

**Advisor:** **Emissions.** Distance × a published emission factor per passenger-kilometre. Factors come from UK DESNZ/DEFRA Greenhouse Gas Reporting: Conversion Factors 2023, business travel tables, bundled offline in this build. Straight-line distance is multiplied by a route-circuity factor (1.20 rail, 1.25 road, 1.05 air plus a 40 km routing allowance), because trains and roads don't travel in straight lines.

**Advisor:** **Ranking.** A weighted sum of three min-max normalised criteria. On your **balanced** profile that's emissions 40%, cost 30%, journey time 30%. Options over your budget are demoted rather than hidden.

**Advisor:** **Accommodation.** Ranked on certification credibility (audited against a GSTC-recognised standard beats audited, which beats self-declared), renewable electricity share, walking distance to transit, local sourcing and price.

**Advisor:** **And what these numbers are not.**

They're fleet averages, not measurements of your specific journey — load factor, aircraft type and electricity mix all move the real figure. Accommodation emissions use a flat 12 kg per person per night, which is a rough European hotel average and nothing more. Availability, prices and certifications in this build come from a bundled demonstration dataset, so treat them as illustrative rather than bookable.

If a number matters to a real decision, check it against the operator's own reporting.

> Quick replies: `Carry on planning` · `Talk to a human advisor`

<sub>round trip 69 ms</sub>

**Traveller:** what do you do with my data?

**Advisor:** **What I hold.** Only what you've told me for this trip: origin, destination, dates, group size, budget and your sustainability preference. If you shared your location, it's used to work out a starting point and is not kept afterwards.

**Where it goes.** Nowhere, unless you ask for a human advisor — and then only the trip brief, the options I showed you and a transcript, with email addresses, phone numbers and ID-like numbers stripped out automatically before sending.

**How long.** The conversation is held in memory for this session and expires after 60 minutes of inactivity. There's no advertising or profiling on any of it.

**Your rights.** Say "start over" and I'll erase everything I'm holding right now.

> Quick replies: `Erase and start over` · `Carry on planning`

<sub>round trip 73 ms</sub>

---
Latency: median 71 ms · p95 73 ms · max 78 ms