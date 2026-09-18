/** Thin client for the Rasa REST channel.
 *
 *  Handles the three things the bare fetch call does not: a hard timeout that
 *  matches the sub-three-second non-functional requirement, one retry on a
 *  transport-level failure, and a typed result the UI can render instead of
 *  throwing.
 */

import type { RasaResponse } from "./types";

const BASE = (import.meta.env.VITE_RASA_URL as string | undefined) ?? "/rasa";
const ENDPOINT = `${BASE.replace(/\/$/, "")}/webhooks/rest/webhook`;

/** Budget for a single attempt. Two attempts stay inside a ~6 s worst case. */
const REQUEST_TIMEOUT_MS = 12_000;

export interface SendOptions {
  sender: string;
  message: string;
  metadata?: Record<string, unknown>;
  signal?: AbortSignal;
}

export type SendResult =
  | { ok: true; responses: RasaResponse[]; latencyMs: number }
  | { ok: false; error: string };

export async function sendMessage(options: SendOptions): Promise<SendResult> {
  const started = performance.now();

  for (let attempt = 0; attempt < 2; attempt += 1) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    // Propagate an outer cancellation (component unmount) into this attempt.
    const onAbort = () => controller.abort();
    options.signal?.addEventListener("abort", onAbort);

    try {
      const response = await fetch(ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sender: options.sender,
          message: options.message,
          metadata: options.metadata ?? {},
        }),
        signal: controller.signal,
      });

      if (!response.ok) {
        // 4xx will not fix itself on a retry; 5xx might.
        if (response.status < 500 || attempt === 1) {
          return { ok: false, error: `The assistant returned ${response.status}.` };
        }
        continue;
      }

      const body = (await response.json()) as RasaResponse[];
      return {
        ok: true,
        responses: Array.isArray(body) ? body : [],
        latencyMs: Math.round(performance.now() - started),
      };
    } catch (error) {
      if (options.signal?.aborted) return { ok: false, error: "cancelled" };
      if (attempt === 1) {
        const aborted = error instanceof DOMException && error.name === "AbortError";
        return {
          ok: false,
          error: aborted
            ? "The assistant took too long to answer."
            : "I couldn't reach the assistant. Check that the Rasa server is running.",
        };
      }
    } finally {
      window.clearTimeout(timer);
      options.signal?.removeEventListener("abort", onAbort);
    }
  }

  return { ok: false, error: "The assistant is unavailable." };
}

/** Stable per-browser conversation id, so a refresh keeps the same session. */
export function conversationId(): string {
  const KEY = "eco-travel-advisor:sender";
  try {
    const existing = window.sessionStorage.getItem(KEY);
    if (existing) return existing;
    const fresh = `web-${crypto.randomUUID()}`;
    window.sessionStorage.setItem(KEY, fresh);
    return fresh;
  } catch {
    // Private mode or blocked storage: fall back to an in-memory id.
    return `web-${Math.random().toString(36).slice(2)}`;
  }
}

/** Ask the browser for coordinates, for the "Use my location" quick reply. */
export function requestLocation(): Promise<{ latitude: number; longitude: number } | null> {
  return new Promise((resolve) => {
    if (!("geolocation" in navigator)) return resolve(null);
    navigator.geolocation.getCurrentPosition(
      (position) =>
        resolve({
          // Two decimal places is roughly 1 km: enough to pick a city, not
          // enough to identify a household. Data minimisation by construction.
          latitude: Number(position.coords.latitude.toFixed(2)),
          longitude: Number(position.coords.longitude.toFixed(2)),
        }),
      () => resolve(null),
      { timeout: 8000, maximumAge: 300_000, enableHighAccuracy: false },
    );
  });
}
