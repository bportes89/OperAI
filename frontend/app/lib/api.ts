const API = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8001").replace(
  /\/$/,
  "",
);
export const SESSION_KEY = "operai_session";

export type Tokens = {
  access_token: string;
  refresh_token: string;
  token_type?: string;
};

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export function getSession(): Tokens | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Tokens;
  } catch {
    return null;
  }
}

export function setSession(tokens: Tokens | null) {
  if (typeof window === "undefined") return;
  if (!tokens) {
    localStorage.removeItem(SESSION_KEY);
    return;
  }
  localStorage.setItem(SESSION_KEY, JSON.stringify(tokens));
}

function emitBillingDenied() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent("operai:billing-denied"));
}

function messageFromBody(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object") return fallback;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
  return fallback;
}

export async function api(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }

  let tokens = getSession();
  if (tokens?.access_token) {
    headers.set("Authorization", `Bearer ${tokens.access_token}`);
  }

  let response: Response;
  try {
    response = await fetch(`${API}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(
      "Não foi possível conectar à API. Verifique se o backend está online.",
      0,
    );
  }

  if (response.status === 401 && tokens?.refresh_token) {
    const refreshed = await fetch(`${API}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: tokens.refresh_token }),
    });
    if (refreshed.ok) {
      const next = (await refreshed.json()) as Tokens;
      setSession(next);
      tokens = next;
      headers.set("Authorization", `Bearer ${next.access_token}`);
      response = await fetch(`${API}${path}`, { ...init, headers });
    } else {
      setSession(null);
    }
  }

  if (response.status === 402) {
    emitBillingDenied();
  }

  return response;
}

export async function apiJson<T = unknown>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await api(path, init);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ApiError(
      messageFromBody(body, "Não foi possível concluir a operação."),
      response.status,
      body,
    );
  }
  return body as T;
}

export async function login(data: {
  email: string;
  password: string;
  organization_slug: string;
}): Promise<Tokens> {
  const tokens = await apiJson<Tokens>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(data),
  });
  setSession(tokens);
  return tokens;
}

export async function register(data: {
  name: string;
  email: string;
  password: string;
  organization_name: string;
  organization_slug: string;
}): Promise<Tokens> {
  const tokens = await apiJson<Tokens>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(data),
  });
  setSession(tokens);
  return tokens;
}

export function logout() {
  setSession(null);
}
