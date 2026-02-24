const API_KEY_STORAGE = "az-telemetry-api-key";

let apiKey = localStorage.getItem(API_KEY_STORAGE) ?? "";

export function getApiKey(): string {
  return apiKey;
}

export function setApiKey(key: string): void {
  apiKey = key;
  localStorage.setItem(API_KEY_STORAGE, key);
}

export async function apiFetch<T>(path: string): Promise<T> {
  const headers: Record<string, string> = {};
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }

  const res = await fetch(path, {
    headers,
    credentials: "same-origin",
  });

  if (res.status === 401) {
    throw new AuthError("Unauthorized");
  }
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return res.json();
}

/** Sentinel error for 401 responses. */
export class AuthError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AuthError";
  }
}

// Auth helpers

export interface AuthUser {
  login: string;
  avatar: string;
}

export async function fetchAuthUser(): Promise<AuthUser | null> {
  try {
    const res = await fetch("/api/auth/user", { credentials: "same-origin" });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function logout(): Promise<void> {
  await fetch("/api/auth/logout", {
    method: "POST",
    credentials: "same-origin",
  });
}

// API response types

export interface OverviewResponse {
  today: {
    date: string;
    total: number;
    human: number;
    claude: number;
    errors: number;
  };
  recent_errors: TelemetryEvent[];
}

export interface WeeklyResponse {
  days: DaySummary[];
}

export interface DaySummary {
  date: string;
  total: number;
  human: number;
  claude: number;
  errors: number;
}

export interface TelemetryEvent {
  pk?: string;
  sk?: string;
  event_type: string;
  actor: string;
  repo?: string;
  timestamp?: string;
  user?: string;
  metadata?: Record<string, unknown>;
}

export interface EventsResponse {
  items: TelemetryEvent[];
  lastKey?: Record<string, unknown>;
}

export interface RepoSummaryResponse {
  repo: string;
  total_events: number;
  by_actor: { human: number; claude: number };
  by_event_type: Record<string, number>;
  daily_activity: { date: string; count: number }[];
  recent_events: TelemetryEvent[];
}
