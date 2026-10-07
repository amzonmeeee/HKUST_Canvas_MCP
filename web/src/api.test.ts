import { describe, expect, it, vi } from "vitest";
import { api, initializeSession } from "./api";

const response = (body: unknown, status = 200) =>
  ({ status, ok: status < 400, json: async () => body }) as Response;

describe("local API transport", () => {
  it("removes launch secrets from browser history, shares concurrent bootstrap and adds CSRF only to mutations", async () => {
    window.history.replaceState(null, "", "/#session=synthetic-launch");
    const fetcher = vi
      .fn()
      .mockResolvedValue(response({ csrf_token: "synthetic-csrf" }));
    vi.stubGlobal("fetch", fetcher);
    await Promise.all([initializeSession(), initializeSession()]);
    expect(window.location.hash).toBe("");
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher.mock.calls[0][1].headers.Authorization).toBe(
      "Bearer synthetic-launch",
    );
    fetcher.mockResolvedValue(response({ id: "synthetic" }));
    await api("/api/workspaces", {
      method: "POST",
      body: { title: "Synthetic" },
    });
    expect(fetcher.mock.lastCall?.[1].headers["X-Workbench-CSRF"]).toBe(
      "synthetic-csrf",
    );
    expect(fetcher.mock.lastCall?.[1].credentials).toBe("same-origin");
    await api("/api/workspaces");
    expect(
      fetcher.mock.lastCall?.[1].headers["X-Workbench-CSRF"],
    ).toBeUndefined();
  });
  it("reconnects using the HttpOnly session rather than retaining a launch token", async () => {
    window.history.replaceState(null, "", "/");
    const fetcher = vi
      .fn()
      .mockResolvedValue(response({ csrf_token: "new-synthetic-csrf" }));
    vi.stubGlobal("fetch", fetcher);
    await initializeSession();
    expect(fetcher.mock.calls[0][1].headers).toBeUndefined();
  });
  it("surfaces actionable API errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          response(
            { error: { code: "canvas_unavailable", message: "Retry Canvas." } },
            502,
          ),
        ),
    );
    await expect(api("/api/canvas/courses")).rejects.toMatchObject({
      message: "Retry Canvas.",
      code: "canvas_unavailable",
      status: 502,
    });
  });
  it("accepts empty successful delete responses", async () => {
    const json = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ status: 204, ok: true, json }),
    );
    expect(
      await api("/api/workspaces/synthetic", { method: "DELETE" }),
    ).toBeUndefined();
    expect(json).not.toHaveBeenCalled();
  });
});
