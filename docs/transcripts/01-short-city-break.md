# Scenario: 01 short city break

**Traveller:** hi there

**Advisor:** Hi — I'm the Eco-Travel Advisor. I help you plan a trip with a much smaller carbon footprint: low-emission routes, certified accommodation and local experiences that keep money in the community.

I'll estimate emissions for each option and show you exactly how I got the number. Where would you like to go?

> Quick replies: `Plan a trip` · `Compare travel emissions` · `How do you calculate this?`

<sub>round trip 42 ms</sub>

**Traveller:** I want to plan a low carbon city break

**Advisor:** Where would you like to travel to?

> Quick replies: `Lisbon` · `Copenhagen` · `Ljubljana` · `Somewhere else`

<sub>round trip 65 ms</sub>

**Traveller:** Copenhagen

**Advisor:** And where are you starting from? You can share your location instead if that's easier.

> Quick replies: `Use my location`

<sub>round trip 65 ms</sub>

**Traveller:** I'm coming from Hamburg

**Advisor:** When do you want to leave? A date like 12 May 2027, or something like "in three weeks", both work.

<sub>round trip 70 ms</sub>

**Traveller:** 12 May 2027

**Advisor:** And when are you coming back?

<sub>round trip 70 ms</sub>

**Traveller:** back on 16 May 2027

**Advisor:** Roughly what's your total budget for the trip, per person, in euros?

> Quick replies: `Under €300` · `€300-700` · `€700+`

<sub>round trip 74 ms</sub>

**Traveller:** 2

**Advisor:** €2 per person is below what almost any trip costs. Shall I work with that anyway?

**Advisor:** Last one. How strictly do you want me to weight environmental impact against cost and travel time?

> Quick replies: `Strict — lowest emissions wins` · `Balanced — trade off sensibly` · `Flexible — cost and time matter more`

<sub>round trip 70 ms</sub>

**Traveller:** about 700 euros

**Advisor:** Pick whichever is closest — I'll use it to weight the ranking.

> Quick replies: `Strict` · `Balanced` · `Flexible`

**Advisor:** Last one. How strictly do you want me to weight environmental impact against cost and travel time?

> Quick replies: `Strict — lowest emissions wins` · `Balanced — trade off sensibly` · `Flexible — cost and time matter more`

<sub>round trip 75 ms</sub>

**Traveller:** balanced please

**Advisor:** Got it. Working out your options now — one moment.

**Advisor:** Hamburg to Copenhagen is about 289 km in a straight line. Here's how the options compare for 2 travellers, weighted for a **balanced** profile.

**[transport comparison card]**

| Mode | CO₂e/person | Cost | Time | Band |
|---|---|---|---|---|
| Long-distance coach | 10 kg | €22 | 6 h | low |
| Petrol car (2 people) | 31 kg | €13 | 4 h | moderate |
| High-speed rail | 5 kg | €55 | 3 h | low |
| Electric car (EU grid) | 17 kg | €32 | 4 h | low |
| National rail | 12 kg | €45 | 4 h | low |
| Ferry (foot passenger) | 7 kg | €35 | 13 h | low |
| Petrol car (1 person) | 62 kg | €51 | 4 h | moderate |
| Domestic flight | 84 kg | €75 | 4 h | moderate |

_Figures from the bundled demonstration dataset — illustrative, not live._

**Advisor:** **Long-distance coach** comes out on top: about **10 kg CO₂e** per person, €22, roughly 6 hours door to door. That's 75 kg less per person than domestic flight — 149 kg across your group.

**Advisor:** What would you like to look at next?

> Quick replies: `Places to stay` · `Things to do` · `Full summary` · `Talk to a human advisor`

<sub>round trip 164 ms</sub>

**Traveller:** where should I stay?

**Advisor:** Places to stay in Copenhagen for 4 nights, aiming under about €110 a night.

**[accommodation carousel]**

| Property | Certification | Per night | Band |
|---|---|---|---|
| Vesterbro Rail Hostel | Travelife | €71 | low |
| Havn Organic Rooms | EU Ecolabel | €127 | low |
| Nørrebro Passivhus Hotel | Green Key | €158 | low |
| Kongens Grand Hotel | — | €210 | high |

_Figures from the bundled demonstration dataset — illustrative, not live._

**Advisor:** **Vesterbro Rail Hostel** ranks first — ranked for independently audited under Travelife, 2 min walk to public transport and among the cheaper options here. About €71 a night, so roughly €284 for the stay.

**Advisor:** What would you like to look at next?

> Quick replies: `Places to stay` · `Things to do` · `Full summary` · `Talk to a human advisor`

<sub>round trip 85 ms</sub>

**Traveller:** what can I do there?

**Advisor:** Things to do in Copenhagen that keep impact low and money local:

**[experience list]**

- Harbour swim and sauna circuit — very low impact, €12, moderate local benefit
- Nørrebro food-waste supper club — very low impact, €26, high local benefit
- Amager Fælled nature reserve by metro — very low impact, free, low local benefit
- Cargo-bike architecture tour — very low impact, €35, high local benefit
- Louisiana museum by regional train — low impact, €24, moderate local benefit

**Advisor:** What would you like to look at next?

> Quick replies: `Places to stay` · `Things to do` · `Full summary` · `Talk to a human advisor`

<sub>round trip 85 ms</sub>

**Traveller:** give me the full summary

**[trip summary card]** Hamburg → Copenhagen

- Total: **68 kg CO₂e per traveller** (135 kg group), band `moderate`
- Travel 20 kg · stay 48 kg
- Estimated cost €328 per person

**Advisor:** All in, about **68 kg CO₂e per traveller** (135 kg for the group): 20 kg travelling and 48 kg for 4 nights of accommodation. Ask me how I worked that out any time.

> Quick replies: `How did you calculate this?` · `Offset the remainder` · `Talk to a human advisor`

<sub>round trip 88 ms</sub>

---
Latency: median 72 ms · p95 88 ms · max 164 ms