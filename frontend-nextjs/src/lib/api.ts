const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5050";

export interface Status {
  running: boolean;
  uptime: number;
  people_count: number;
  alert: boolean;
  alert_type: string;
  message: string;
  severity: string;
  ai_insight: string;
  fps: number;
  frame_count: number;
  source_mode: string;
  source_name: string;
  periodic_summary: string | null;
  internet_connected: boolean;
  loading_progress: number;
}

export interface Event {
  id: string;
  type: string;
  message: string;
  severity: string;
  people_count: number;
  timestamp: string;
  ai_insight?: string;
}

async function call<T>(
  method: string,
  path: string,
  body?: object
): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store",
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err?.error || `HTTP ${res.status}`);
    }
    return res.json() as T;
  } catch (e) {
    console.debug(`[API] ${method} ${path}`, e);
    return null;
  }
}

export const api = {
  health: () => call<{ status: string; uptime: number }>("GET", "/health"),
  status: () => call<Status>("GET", "/status"),
  getVideos: () => call<string[]>("GET", "/videos"),
  events: (n = 30) => call<Event[]>("GET", `/events?n=${n}`),
  clearEvents: () => call<{ status: string }>("POST", "/events/clear"),
  start: (mode: string, source: string) =>
    call<{ status: string; error?: string; mode?: string; source?: string }>("POST", "/start", { mode, source }),
  stop: () => call<{ status: string }>("POST", "/stop"),
  settings: (s: object) => call<{ status: string }>("POST", "/settings", s),
  getSettings: () => call<any>("GET", "/settings"),
  testEmail: (config: object) => call<{ status?: string, error?: string }>("POST", "/settings/test_email", config),
  // MUST point directly to backend to avoid Next.js glitchy streaming proxy
  streamUrl: () => `${API_BASE}/video_feed`,
};
