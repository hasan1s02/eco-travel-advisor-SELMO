/** Renderers for every custom payload the action server can send.
 *
 *  Design rules applied throughout (section 3 of the assignment brief):
 *  - The green / amber / red band always appears as colour, a word AND an
 *    icon. Colour alone would fail WCAG 1.4.1 and would be useless to roughly
 *    one in twelve male travellers.
 *  - Every card ends with a provenance line. A sustainability tool that hides
 *    where its numbers came from is doing the thing it claims to prevent.
 *  - Nothing is presented as booked, verified or guaranteed unless the data
 *    actually says so; "unknown" is rendered as unknown.
 */

import type {
  Band,
  CustomPayload,
  Experience,
  Hotel,
  OffsetProvider,
  TransportOption,
} from "../lib/types";
import { AgentIcon, InfoIcon, ModeIcon, WarningIcon } from "./Icons";

const BAND_LABEL: Record<Band, string> = {
  low: "Low emissions",
  moderate: "Moderate emissions",
  high: "High emissions",
};

const BAND_GLYPH: Record<Band, string> = { low: "●", moderate: "◐", high: "○" };

const euro = (n: number | null | undefined) =>
  n == null ? "—" : new Intl.NumberFormat("en-IE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(n);

const hours = (h: number) => (h < 1 ? `${Math.round(h * 60)} min` : h < 10 ? `${h.toFixed(1)} h` : `${Math.round(h)} h`);

function BandBadge({ band }: { band: Band }) {
  return (
    <span className={`badge badge--${band}`}>
      <span aria-hidden="true">{BAND_GLYPH[band]}</span>
      {BAND_LABEL[band]}
    </span>
  );
}

function Provenance({ text }: { text: string }) {
  return <p className="card__foot">{text}</p>;
}

/* ====================================================================== */
/* Transport comparison                                                    */
/* ====================================================================== */
function TransportOptions({
  payload,
  onSelect,
}: {
  payload: Extract<CustomPayload, { type: "transport_options" }>;
  onSelect: (text: string) => void;
}) {
  const worst = Math.max(...payload.options.map((o) => o.kg_co2e_per_traveller), 1);
  const weights = payload.weights;

  return (
    <section className="card" aria-labelledby="transport-heading">
      <header className="card__head">
        <h3 className="card__title" id="transport-heading">
          {payload.origin} → {payload.destination}
        </h3>
        <p className="card__meta">
          {payload.options.length} options for {payload.travellers} traveller
          {payload.travellers > 1 ? "s" : ""} · weighted {Math.round((weights.carbon ?? 0) * 100)}% emissions,{" "}
          {Math.round((weights.cost ?? 0) * 100)}% cost, {Math.round((weights.time ?? 0) * 100)}% time
        </p>
      </header>

      <ul className="options">
        {payload.options.map((option, index) => (
          <li key={option.mode_key}>
            <OptionRow option={option} best={index === 0} worst={worst} onSelect={onSelect} />
          </li>
        ))}
      </ul>

      <Provenance text={payload.provenance} />
    </section>
  );
}

function OptionRow({
  option,
  best,
  worst,
  onSelect,
}: {
  option: TransportOption;
  best: boolean;
  worst: number;
  onSelect: (text: string) => void;
}) {
  const share = Math.max((option.kg_co2e_per_traveller / worst) * 100, 2);

  // One sentence that stands alone for a screen-reader user, who will not see
  // the bar, the colour or the column alignment.
  const label =
    `${option.label}. ${BAND_LABEL[option.band]}. ` +
    `${option.kg_co2e_per_traveller.toFixed(0)} kilograms CO2 equivalent per traveller, ` +
    `about ${euro(option.cost_eur_per_traveller)}, ${hours(option.duration_h)} door to door. ` +
    `${option.rationale}` +
    (best ? " Ranked first for your preferences." : "");

  return (
    <button
      type="button"
      className={`option${best ? " option--best" : ""}`}
      data-band={option.band}
      aria-label={label}
      onClick={() => onSelect(`Tell me more about travelling by ${option.label.toLowerCase()}`)}
    >
      <span className="option__icon" aria-hidden="true">
        <ModeIcon name={option.icon} />
      </span>

      <span>
        <span className="option__name">
          {option.label}
          {best && <span className="badge badge--best">Best match</span>}
          <BandBadge band={option.band} />
        </span>
        <span className="option__detail">
          {euro(option.cost_eur_per_traveller)} · {hours(option.duration_h)} · {Math.round(option.distance_km)} km
        </span>
        <span className="option__why">{option.rationale}</span>
        {option.notes.map((note) => (
          <span className="option__why" key={note}>
            {note}
          </span>
        ))}
        <span className="bar" aria-hidden="true">
          <span className="bar__fill" style={{ width: `${share}%` }} />
        </span>
      </span>

      <span className="option__figure" aria-hidden="true">
        <span className="option__co2">{option.kg_co2e_per_traveller.toFixed(0)}</span>
        <span className="option__unit">kg CO₂e</span>
      </span>
    </button>
  );
}

/* ====================================================================== */
/* Accommodation carousel                                                  */
/* ====================================================================== */
function HotelCarousel({ payload }: { payload: Extract<CustomPayload, { type: "hotel_carousel" }> }) {
  return (
    <section className="card" aria-labelledby="hotels-heading">
      <header className="card__head">
        <h3 className="card__title" id="hotels-heading">
          Where to stay in {payload.destination}
        </h3>
        <p className="card__meta">
          {payload.hotels.length} properties
          {payload.nights ? ` · ${payload.nights} night${payload.nights === 1 ? "" : "s"}` : ""}
          {payload.nightly_budget_eur ? ` · target under ${euro(payload.nightly_budget_eur)} a night` : ""}
        </p>
      </header>

      {/* A horizontally scrolling region needs to be reachable and
          announced; role="group" plus tabIndex makes it keyboard-scrollable. */}
      <ul
        className="carousel"
        role="group"
        aria-label={`Accommodation options in ${payload.destination}, scrollable horizontally`}
        tabIndex={0}
        style={{ listStyle: "none", margin: 0 }}
      >
        {payload.hotels.map((hotel) => (
          <li key={hotel.id ?? hotel.name} style={{ display: "contents" }}>
            <HotelCard hotel={hotel} nights={payload.nights} />
          </li>
        ))}
      </ul>

      <Provenance text={payload.provenance} />
    </section>
  );
}

function HotelCard({ hotel, nights }: { hotel: Hotel; nights: number }) {
  const certLabel =
    hotel.cert_status === "unknown"
      ? "Certification unverified"
      : hotel.cert
        ? `${hotel.cert}${(hotel.cert_tier ?? 3) === 1 ? " (GSTC-recognised)" : ""}`
        : "No certification claimed";

  const certBadge: Band | "neutral" =
    hotel.cert_status === "unknown" ? "neutral" : (hotel.cert_tier ?? 3) === 1 ? "low" : hotel.cert ? "moderate" : "high";

  return (
    <article className="hotel" data-band={hotel.band} aria-label={`${hotel.name}. ${certLabel}. ${hotel.rationale}`}>
      <div className="hotel__name">{hotel.name}</div>

      <span className={`badge badge--${certBadge}`}>{certLabel}</span>

      <div className="hotel__price">
        {euro(hotel.price_eur)} <span>/ night{nights ? ` · ${euro((hotel.price_eur ?? 0) * nights)} total` : ""}</span>
      </div>

      <p className="hotel__summary">{hotel.summary}</p>

      <ul className="hotel__attrs">
        {hotel.energy != null && <li>{Math.round(hotel.energy * 100)}% renewable electricity</li>}
        {hotel.transit_min != null && <li>{hotel.transit_min} min walk to transit</li>}
        {hotel.local_sourcing != null && <li>{Math.round(hotel.local_sourcing * 100)}% food sourced locally</li>}
        {hotel.single_use_plastic_free && <li>No single-use plastics in guest areas</li>}
      </ul>

      {hotel.notes.map((note) => (
        <p className="hotel__note" key={note}>
          {note}
        </p>
      ))}
    </article>
  );
}

/* ====================================================================== */
/* Experiences and offsets                                                 */
/* ====================================================================== */
const IMPACT_LABEL: Record<Experience["impact"], string> = {
  very_low: "Very low impact",
  low: "Low impact",
  moderate: "Moderate impact",
};

function ExperienceList({ payload }: { payload: Extract<CustomPayload, { type: "experience_list" }> }) {
  return (
    <section className="card" aria-labelledby="experiences-heading">
      <header className="card__head">
        <h3 className="card__title" id="experiences-heading">
          Things to do in {payload.destination}
        </h3>
        <p className="card__meta">Ranked for low impact and local benefit</p>
      </header>

      <ul className="tiles">
        {payload.experiences.map((item) => (
          <li className="tile" key={item.id}>
            <div className="tile__head">
              <span className="tile__name">{item.name}</span>
              <span className="tile__price">{item.price_eur === 0 ? "Free" : euro(item.price_eur)}</span>
            </div>
            <div style={{ display: "flex", gap: 6, marginTop: 5, flexWrap: "wrap" }}>
              <span className={`badge badge--${item.impact === "moderate" ? "moderate" : "low"}`}>
                {IMPACT_LABEL[item.impact]}
              </span>
              <span className="badge badge--neutral">{item.community_benefit} local benefit</span>
              <span className="badge badge--neutral">{hours(item.duration_h)}</span>
            </div>
            <p className="tile__summary">{item.summary}</p>
          </li>
        ))}
      </ul>

      <Provenance text={payload.provenance} />
    </section>
  );
}

function OffsetList({ payload }: { payload: Extract<CustomPayload, { type: "offset_list" }> }) {
  return (
    <section className="card" aria-labelledby="offsets-heading">
      <header className="card__head">
        <h3 className="card__title" id="offsets-heading">
          Contribution options for {payload.residual_kg_co2e.toFixed(0)} kg CO₂e
        </h3>
        <p className="card__meta">Shown after reduction options, never instead of them</p>
      </header>

      <ul className="tiles">
        {payload.providers.map((provider: OffsetProvider) => (
          <li className="tile" key={provider.id}>
            <div className="tile__head">
              <span className="tile__name">{provider.type}</span>
              <span className="tile__price">{euro(provider.estimated_cost_eur)}</span>
            </div>
            <div style={{ display: "flex", gap: 6, marginTop: 5, flexWrap: "wrap" }}>
              <span className="badge badge--neutral">{provider.standard}</span>
              <span
                className={`badge badge--${
                  provider.confidence === "high" ? "low" : provider.confidence === "medium" ? "moderate" : "high"
                }`}
              >
                {provider.confidence} confidence
              </span>
              <span className="badge badge--neutral">{euro(provider.eur_per_tonne)}/tonne</span>
            </div>
            <p className="tile__summary">Permanence: {provider.permanence}</p>
            <p className="tile__caveat">{provider.caveat}</p>
          </li>
        ))}
      </ul>

      <Provenance text={payload.provenance} />
    </section>
  );
}

/* ====================================================================== */
/* Trip summary                                                            */
/* ====================================================================== */
function TripSummary({ payload }: { payload: Extract<CustomPayload, { type: "trip_summary" }> }) {
  const f = payload.footprint;
  const journeyShare = f.total_kg_per_traveller ? (f.journey_kg_per_traveller / f.total_kg_per_traveller) * 100 : 100;

  return (
    <section className="card" aria-labelledby="summary-heading">
      <header className="card__head">
        <h3 className="card__title" id="summary-heading">
          {payload.origin ?? "—"} → {payload.destination}
        </h3>
        <p className="card__meta">
          {payload.departure_date ?? "dates open"}
          {payload.return_date ? ` to ${payload.return_date}` : ""} · {payload.travellers} traveller
          {payload.travellers > 1 ? "s" : ""}
          {payload.sustainability_level ? ` · ${payload.sustainability_level} profile` : ""}
        </p>
      </header>

      <div className="summary">
        <div className="summary__hero" data-band={f.band}>
          <span className="summary__figure">{f.total_kg_per_traveller.toFixed(0)}</span>
          <span>
            kg CO₂e per traveller
            <br />
            <strong>{f.total_kg_group.toFixed(0)} kg</strong> across the group
          </span>
          <span style={{ marginLeft: "auto" }}>
            <BandBadge band={f.band} />
          </span>
        </div>

        <div>
          <div
            className="summary__split"
            role="img"
            aria-label={`Footprint split: ${f.journey_kg_per_traveller.toFixed(0)} kilograms travelling, ${f.stay_kg_per_traveller.toFixed(0)} kilograms accommodation`}
          >
            <span
              className="summary__seg"
              style={{ width: `${journeyShare}%`, background: "var(--band-moderate-bg)" }}
            >
              Travel {f.journey_kg_per_traveller.toFixed(0)}
            </span>
            <span
              className="summary__seg"
              style={{ width: `${100 - journeyShare}%`, background: "var(--band-low-bg)" }}
            >
              Stay {f.stay_kg_per_traveller.toFixed(0)}
            </span>
          </div>
        </div>

        <div className="summary__grid">
          <div className="summary__cell">
            <div className="summary__label">Travelling by</div>
            <div className="summary__value">{payload.transport?.label ?? "Not chosen"}</div>
          </div>
          <div className="summary__cell">
            <div className="summary__label">Staying at</div>
            <div className="summary__value">{payload.accommodation?.name ?? "Not chosen"}</div>
          </div>
          <div className="summary__cell">
            <div className="summary__label">Nights</div>
            <div className="summary__value">{payload.nights || "—"}</div>
          </div>
          <div className="summary__cell">
            <div className="summary__label">Est. cost per person</div>
            <div className="summary__value">{euro(payload.estimated_cost_eur_per_traveller)}</div>
          </div>
        </div>
      </div>

      <Provenance text={payload.provenance} />
    </section>
  );
}

/* ====================================================================== */
/* Alerts and handover                                                     */
/* ====================================================================== */
function AlertCard({ payload }: { payload: Extract<CustomPayload, { type: "alert" }> }) {
  const warning = payload.level === "warning";
  return (
    <div className={`alert alert--${payload.level}`} role={warning ? "alert" : "note"}>
      <span aria-hidden="true" style={{ flex: "none", marginTop: 1 }}>
        {warning ? <WarningIcon /> : <InfoIcon />}
      </span>
      <div>
        <p className="alert__title">{payload.title}</p>
        <p className="alert__body">{payload.body}</p>
      </div>
    </div>
  );
}

function HandoverCard({ payload }: { payload: Extract<CustomPayload, { type: "handover" }> }) {
  const brief = payload.trip_brief as Record<string, unknown>;
  const rows: [string, unknown][] = [
    ["Route", `${brief.origin ?? "—"} → ${brief.destination ?? "—"}`],
    ["Dates", `${brief.departure_date ?? "—"} to ${brief.return_date ?? "—"}`],
    ["Travellers", brief.travellers ?? "—"],
    ["Budget", brief.budget_eur ? euro(Number(brief.budget_eur)) : "—"],
    ["Priority", brief.sustainability_level ?? "—"],
  ];

  return (
    <div className="handover" role="status">
      <div className="handover__row">
        <span className="handover__pulse" aria-hidden="true" />
        <AgentIcon />
        <span className="handover__title">
          {payload.status === "delivered" ? "Handed to a human advisor" : "Advisor desk unreachable"}
        </span>
        <span className="handover__ref" style={{ marginLeft: "auto" }}>
          {payload.reference}
        </span>
      </div>

      <dl className="handover__brief">
        {rows.map(([label, value]) => (
          <div key={label} style={{ display: "flex", gap: 8 }}>
            <dt style={{ minWidth: 92 }}>{label}</dt>
            <dd style={{ margin: 0 }}>{String(value)}</dd>
          </div>
        ))}
      </dl>

      {payload.advisor_notes.length > 0 && (
        <ul className="handover__notes">
          {payload.advisor_notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

/* ====================================================================== */
/* Dispatcher                                                              */
/* ====================================================================== */
export function CustomCard({
  payload,
  onSelect,
}: {
  payload: CustomPayload;
  onSelect: (text: string) => void;
}) {
  switch (payload.type) {
    case "transport_options":
      return <TransportOptions payload={payload} onSelect={onSelect} />;
    case "hotel_carousel":
      return <HotelCarousel payload={payload} />;
    case "experience_list":
      return <ExperienceList payload={payload} />;
    case "offset_list":
      return <OffsetList payload={payload} />;
    case "trip_summary":
      return <TripSummary payload={payload} />;
    case "alert":
      return <AlertCard payload={payload} />;
    case "handover":
      return <HandoverCard payload={payload} />;
    default:
      // An unrecognised payload means the Python side got ahead of the UI.
      // Render nothing rather than crash the transcript.
      return null;
  }
}
