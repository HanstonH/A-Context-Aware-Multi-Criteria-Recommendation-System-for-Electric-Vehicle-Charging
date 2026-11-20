// Client for the MapExplore backend (backend/ in the repo, deployed on Railway).
// Set EXPO_PUBLIC_API_URL in app/.env. Without it the app runs in offline mode.

import { File } from "expo-file-system";
import type { Lang } from "./i18n";

const BASE = (process.env.EXPO_PUBLIC_API_URL ?? "").trim().replace(/\/+$/, "");
const KEY = (process.env.EXPO_PUBLIC_API_KEY ?? "").trim();

export const backendConfigured = BASE.length > 0;

export class ApiError extends Error {
  status: number; // HTTP status, or 0 for network / timeout / not configured

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

/** Headers every backend call needs (the optional shared key). */
export const authHeaders = (): Record<string, string> => (KEY ? { "X-API-Key": KEY } : {});

/** Full URL for a server path such as "/api/speech/abc". */
export const absoluteUrl = (path: string) => `${BASE}${path}`;

async function request<T>(path: string, body: unknown | null, timeoutMs: number): Promise<T> {
  if (!backendConfigured) throw new ApiError("backend not configured", 0);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const isForm = body instanceof FormData;
  try {
    const res = await fetch(`${BASE}${path}`, {
      method: body === null ? "GET" : "POST",
      // For FormData, fetch sets the multipart Content-Type (with its boundary) itself.
      headers: isForm ? authHeaders() : { "Content-Type": "application/json", ...authHeaders() },
      body: body === null ? undefined : isForm ? body : JSON.stringify(body),
      signal: controller.signal,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new ApiError(data?.error || `HTTP ${res.status}`, res.status);
    return data as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(err instanceof Error ? err.message : "network error", 0);
  } finally {
    clearTimeout(timer);
  }
}

export type Where = {
  lat: number;
  lng: number;
  battery_pct: number;
  lang: Lang;
};

export type ApiStation = {
  id: string;
  name: string;
  lat: number;
  lng: number;
  city: string | null;
  source: string;
  km?: number | null;
};

export type RecResult = ApiStation & {
  rank: number;
  total_score: number;
  distance_m: number;
  duration_s: number | null;
  reachable: boolean;
  cost: { ntd_per_kwh: number | null; known: boolean };
  wait: { seconds: number; placeholder: boolean };
  reasons: string[];
};

export type RecResponse = {
  ok: boolean;
  reason?: string;
  range: { max_range_km: number };
  results: RecResult[];
  wait_is_placeholder?: boolean;
};

export type ChatTurn = { role: "user" | "model"; text: string };

export type ChatResponse = {
  ok: boolean;
  reply: string;
  stations: ApiStation[];
  model: string;
};

export type ExplainResponse = {
  ok: boolean;
  explanation: string;
  source: "gemini" | "rules";
};

export type Health = { ok: boolean; stations: number; gemini: boolean };

export const health = () => request<Health>("/api/health", null, 8000);

export const recommend = (where: Where, opts?: { city?: string; limit?: number }) =>
  request<RecResponse>("/api/recommend", { ...where, ...opts }, 20000);

export const chat = (where: Where, message: string, history: ChatTurn[], destId?: string | null) =>
  request<ChatResponse>(
    "/api/chat",
    { ...where, message, history, dest_id: destId ?? undefined },
    60000
  );

export const explain = (where: Where, stationId: string) =>
  request<ExplainResponse>("/api/explain", { ...where, station_id: stationId }, 45000);

export type SpeechPart = { id: string; url: string; text: string };

export type VoiceResponse = {
  ok: boolean;
  heard: boolean; // false when the recording had no clear speech
  transcript: string;
  reply: string;
  lang?: Lang; // language of the reply: the one the driver spoke, not necessarily the app's
  spoken?: string; // the reply rewritten for reading aloud ("NT$5/kWh" -> "新台幣5每度")
  stations: ApiStation[];
  speech: SpeechPart[]; // Gemini voice only: download each url in order and play it
};

/**
 * Send a recorded question (local file uri, m4a); the server transcribes and answers it.
 * speech "device": the phone reads the reply, so the server skips Gemini text-to-speech.
 */
export function voice(
  where: Where,
  audioUri: string,
  history: ChatTurn[],
  destId: string | null | undefined,
  speech: "gemini" | "device"
): Promise<VoiceResponse> {
  const form = new FormData();
  // Expo SDK 58's fetch (expo/fetch) rejects React Native's { uri, name, type } parts;
  // an expo-file-system File works because it exposes its bytes like a Blob.
  form.append("audio", new File(audioUri));
  form.append("data", JSON.stringify({ ...where, history, dest_id: destId ?? undefined, speech }));
  return request<VoiceResponse>("/api/voice", form, 60000);
}
