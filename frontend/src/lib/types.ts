/** Shapes of the custom payloads emitted by the Rasa action server.
 *
 *  These mirror the `json_message=` dictionaries in actions/actions.py. Keeping
 *  them in one file means a change on the Python side shows up as a TypeScript
 *  error here rather than as a blank card at runtime.
 */

export type Band = "low" | "moderate" | "high";

export interface RasaButton {
  title: string;
  payload: string;
}

export interface TransportOption {
  mode_key: string;
  label: string;
  icon: string;
  distance_km: number;
  kg_co2e_per_traveller: number;
  kg_co2e_total: number;
  cost_eur_per_traveller: number;
  duration_h: number;
  factor_source: string;
  data_source: string;
  degraded: boolean;
  score: number;
  band: Band;
  rationale: string;
  savings_vs_worst_kg: number;
  affordable: boolean;
  notes: string[];
}

export interface Hotel {
  id?: string;
  name: string;
  cert: string | null;
  cert_tier: number | null;
  cert_status?: "verified" | "unknown" | "none_claimed";
  price_eur: number | null;
  energy: number | null;
  single_use_plastic_free: boolean | null;
  transit_min: number | null;
  local_sourcing: number | null;
  district?: string | null;
  summary: string;
  score: number;
  band: Band;
  rationale: string;
  affordable?: boolean;
  notes: string[];
}

export interface Experience {
  id: string;
  name: string;
  impact: "very_low" | "low" | "moderate";
  price_eur: number;
  duration_h: number;
  community_benefit: "low" | "moderate" | "high";
  summary: string;
}

export interface OffsetProvider {
  id: string;
  type: string;
  standard: string;
  eur_per_tonne: number;
  permanence: string;
  confidence: "low" | "medium" | "high";
  caveat: string;
  estimated_cost_eur: number;
}

export type CustomPayload =
  | {
      type: "transport_options";
      origin: string;
      destination: string;
      travellers: number;
      sustainability_level: string;
      weights: Record<string, number>;
      options: TransportOption[];
      provenance: string;
    }
  | {
      type: "hotel_carousel";
      destination: string;
      nights: number;
      nightly_budget_eur: number | null;
      sustainability_level: string;
      hotels: Hotel[];
      provenance: string;
    }
  | { type: "experience_list"; destination: string; experiences: Experience[]; provenance: string }
  | {
      type: "offset_list";
      residual_kg_co2e: number;
      providers: OffsetProvider[];
      provenance: string;
    }
  | {
      type: "trip_summary";
      origin: string | null;
      destination: string;
      departure_date: string | null;
      return_date: string | null;
      nights: number;
      travellers: number;
      sustainability_level: string | null;
      transport: TransportOption | null;
      accommodation: Hotel | null;
      footprint: {
        journey_kg_per_traveller: number;
        stay_kg_per_traveller: number;
        total_kg_per_traveller: number;
        total_kg_group: number;
        band: Band;
      };
      estimated_cost_eur_per_traveller: number;
      provenance: string;
    }
  | { type: "alert"; level: "info" | "warning"; title: string; body: string }
  | {
      type: "handover";
      status: "delivered" | "failed";
      channel: string;
      reference: string;
      reason: string;
      trip_brief: Record<string, unknown>;
      advisor_notes: string[];
    };

/** One rendered turn in the transcript. */
export interface ChatMessage {
  id: string;
  author: "user" | "bot";
  text?: string;
  buttons?: RasaButton[];
  custom?: CustomPayload;
  at: number;
  /** Set when the bot could not be reached, so the UI can offer a retry. */
  failed?: boolean;
}

export interface RasaResponse {
  recipient_id?: string;
  text?: string;
  buttons?: RasaButton[];
  custom?: CustomPayload;
  image?: string;
}
