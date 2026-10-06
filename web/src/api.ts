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

export async function upload<T>(path: string, file: File): Promise<T> {
  const body = new FormData();
  body.append("file", file);
  return decode(
    await fetch(path, {
      method: "POST",
      body,
      credentials: "same-origin",
      headers: { "X-Workbench-CSRF": csrf },
    }),
  );
}

export async function stream(
  path: string,
  body: unknown,
  onEvent: (event: Record<string, unknown>) => void,
  signal: AbortSignal,
): Promise<void> {
  const response = await fetch(path, {
    method: "POST",
    body: JSON.stringify(body),
    credentials: "same-origin",
    signal,
    headers: { "Content-Type": "application/json", "X-Workbench-CSRF": csrf },
  });
  if (!response.ok) {
    await decode(response);
    return;
  }
  if (!response.body)
    throw new Error("Streaming is unavailable in this browser.");
  const reader = response.body.getReader(),
    decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let boundary: number;
      while ((boundary = buffer.indexOf("\n\n")) >= 0) {
        const block = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const data = block
          .split("\n")
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trimStart())
          .join("\n");
        if (data) onEvent(JSON.parse(data));
      }
      if (done) break;
    }
  } finally {
    reader.releaseLock();
  }
}
