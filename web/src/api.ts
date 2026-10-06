let csrf = "";
let pendingSession: Promise<void> | undefined;

export class ApiError extends Error {
  constructor(
    message: string,
    public code: string,
    public status: number,
  ) {
    super(message);
  }
}

async function decode(response: Response) {
  if (response.status === 204) return undefined;
  const result = await response.json();
  if (!response.ok) {
    const message =
      result.error?.message ||
      (typeof result.detail === "string"
        ? result.detail
        : "Check the fields and try again.");
    throw new ApiError(
      message,
      result.error?.code || "request_failed",
      response.status,
    );
  }
  return result;
}

async function establishSession(): Promise<void> {
  const fragment = new URLSearchParams(window.location.hash.slice(1));
  const launch = fragment.get("session");
  if (launch)
    window.history.replaceState(
      null,
      "",
      window.location.pathname + window.location.search,
    );
  const response = await fetch(
    "/api/session",
    launch
      ? {
          method: "POST",
          headers: { Authorization: `Bearer ${launch}` },
          credentials: "same-origin",
        }
      : { credentials: "same-origin" },
  );
  csrf = (await decode(response)).csrf_token;
}

export function initializeSession(): Promise<void> {
  pendingSession ??= establishSession().finally(() => {
    pendingSession = undefined;
  });
  return pendingSession;
}

export async function api<T>(
  path: string,
  options: { method?: string; body?: unknown } = {},
): Promise<T> {
  const method = options.method || "GET";
  const headers: Record<string, string> = {};
  if (method !== "GET") headers["X-Workbench-CSRF"] = csrf;
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  return decode(
    await fetch(path, {
      method,
      headers,
      credentials: "same-origin",
      ...(options.body !== undefined
        ? { body: JSON.stringify(options.body) }
        : {}),
    }),
  );
}
