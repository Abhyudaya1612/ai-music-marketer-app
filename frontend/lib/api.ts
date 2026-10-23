export class ApiError extends Error {
  code: string;
  requestId: string | null;

  constructor(message: string, code = "API_ERROR", requestId: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.requestId = requestId;
  }
}

export function apiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (configured) return configured.replace(/\/$/, "");
  if (typeof window === "undefined") return "http://localhost:8000";
  return `${window.location.protocol}//${window.location.hostname}:8000`;
}

export async function apiRequest<T>(
  path: string,
  token: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof Blob)) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    ...options,
    headers,
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as
      | { error?: { code?: string; message?: string; request_id?: string }; detail?: string }
      | null;
    throw new ApiError(
      body?.error?.message || body?.detail || `Request failed (${response.status}).`,
      body?.error?.code || "API_ERROR",
      body?.error?.request_id || response.headers.get("X-Request-ID"),
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
