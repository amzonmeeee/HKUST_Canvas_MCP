import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import type { Course, Workspace } from "./types";

const course: Course = {
  id: "101",
  name: "Synthetic course",
  course_code: "TEST1000",
  term_name: "Synthetic term",
  canvas_url: "https://canvas.ust.hk/courses/101",
};
const workspace: Workspace = {
  id: "00000000-0000-4000-8000-000000000001",
  kind: "canvas_course",
  canvas_course_id: "101",
  title: "Synthetic course",
  description: "",
  course_code: "TEST1000",
  term_name: "Synthetic term",
  created_at: "2026-01-01",
  updated_at: "2026-01-01",
  last_sync_at: null,
};
let coursesFail = false;
let stored: Workspace[] = [];
let requests: { path: string; method: string; body?: Record<string, string> }[];

beforeEach(() => {
  window.history.replaceState(null, "", "/#session=synthetic-launch");
  coursesFail = false;
  stored = [];
  requests = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, options?: RequestInit) => {
      const method = options?.method || "GET";
      const body = options?.body
        ? JSON.parse(options.body as string)
        : undefined;
      requests.push({ path, method, body });
      let result: unknown;
      let status = 200;
      if (path === "/api/session") result = { csrf_token: "synthetic-csrf" };
      else if (path === "/api/canvas/profiles")
        result = {
          profiles: [
            { id: "Default", name: "Synthetic profile", selected: true },
          ],
        };
      else if (path === "/api/canvas/status")
        result = {
          auth_verified: !coursesFail,
          auth_status: coursesFail ? "unavailable" : "verified",
          profile_name: "Synthetic profile",
          message: "Sign in to Chrome and retry.",
        };
      else if (path === "/api/canvas/courses") {
        result = coursesFail
          ? {
              error: {
                code: "canvas_unavailable",
                message: "Canvas is offline.",
              },
            }
          : { courses: [course], truncated: false };
        if (coursesFail) status = 502;
      } else if (path === "/api/settings")
        result = {
          phase: "A",
          profile_name: "Synthetic profile",
          schema_version: 1,
          mcp_command: "canvas-mcp --transport stdio",
        };
      else if (path === "/api/workspaces" && method === "GET")
        result = { workspaces: stored };
      else if (path === "/api/local-clients")
        result = {
          cli: [],
          desktop: [],
          mcp_config: "{}",
          can_open_login: false,
        };
      else if (path === "/api/providers") result = { providers: [] };
      else if (path.endsWith("/sources")) result = { sources: [] };
      else if (path.endsWith("/conversations")) result = { conversations: [] };
      else if (path.endsWith("/actions")) result = { tools: [], previews: [] };
      else if (path.endsWith("/artifacts")) result = { artifacts: [] };
      else if (path.endsWith("/notes")) result = { notes: [] };
      else if (path === "/api/workspaces" && method === "POST") {
        result = {
          ...workspace,
          ...(body.kind === "custom"
            ? {
                kind: "custom",
                canvas_course_id: null,
                title: body.title,
                description: body.description,
              }
            : {}),
        };
        stored = [result as Workspace];
      } else if (
        path === `/api/workspaces/${workspace.id}` &&
        method === "PATCH"
      ) {
        stored = [{ ...stored[0], ...body }];
        result = stored[0];
      } else if (
        path === `/api/workspaces/${workspace.id}` &&
        method === "DELETE"
      ) {
        stored = [];
        status = 204;
      } else if (path === `/api/workspaces/${workspace.id}`)
        result = stored[0] || workspace;
      else {
        status = 404;
        result = { detail: "Not found" };
      }
      return { status, ok: status < 400, json: async () => result } as Response;
    }),
  );
});

describe("Local workbench foundation", () => {
  it("bootstraps a launch link once even when React StrictMode replays effects", async () => {
    render(
      <StrictMode>
        <App />
      </StrictMode>,
    );
    expect(await screen.findByText("TEST1000")).toBeInTheDocument();
    expect(
      requests.filter(
        (request) =>
          request.path === "/api/session" && request.method === "POST",
      ),
    ).toHaveLength(1);
  });
  it("lists real API courses and filters without additional remote requests", async () => {
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByText("TEST1000")).toBeInTheDocument();
    await user.type(
      screen.getByRole("searchbox", { name: "Find a course" }),
      "missing",
    );
    expect(screen.getByText("No matching courses")).toBeInTheDocument();
    expect(
      requests.filter((request) => request.path === "/api/canvas/courses"),
    ).toHaveLength(1);
  });
  it("opens a course as a persistent local workspace", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(
      await screen.findByRole("button", { name: "Open TEST1000" }),
    );
    expect(
      await screen.findByRole("heading", {
        name: "Synthetic course",
        level: 1,
      }),
    ).toBeInTheDocument();
    expect(
      requests.find(
        (request) =>
          request.method === "POST" && request.path === "/api/workspaces",
      )?.body,
    ).toEqual({ kind: "canvas_course", canvas_course_id: "101" });
    expect(
      await screen.findByRole("button", { name: "Find course sources" }),
    ).toBeInTheDocument();
    expect(
      requests.some(
        (r) => r.path.endsWith("/sync") || r.path.endsWith("/inventory"),
      ),
    ).toBe(false);
  });
  it("creates a custom workspace through an inline form", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(
      await screen.findByRole("button", { name: "New workspace" }),
    );
    await user.type(
      screen.getByRole("textbox", { name: "Workspace name" }),
      "Research reading",
    );
    await user.click(screen.getByRole("button", { name: "Create workspace" }));
    expect(
      await screen.findByRole("heading", {
        name: "Research reading",
        level: 1,
      }),
    ).toBeInTheDocument();
    expect(stored[0].kind).toBe("custom");
  });
  it("keeps local workspaces available when Canvas is offline", async () => {
    coursesFail = true;
    stored = [workspace];
    const user = userEvent.setup();
    render(<App />);
    expect(await screen.findByText("Canvas is offline.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Synthetic course/ }));
    expect(
      await screen.findByRole("heading", {
        name: "Synthetic course",
        level: 1,
      }),
    ).toBeInTheDocument();
    expect(
      requests.filter(
        (request) =>
          request.path === "/api/workspaces" && request.method === "POST",
      ),
    ).toHaveLength(0);
  });
  it("edits workspace metadata and requires a second action before deletion", async () => {
    stored = [workspace];
    window.history.replaceState(
      null,
      "",
      `/workspace/${workspace.id}#session=synthetic-launch`,
    );
    const user = userEvent.setup();
    render(<App />);
    await user.click(
      await screen.findByRole("button", { name: "Edit workspace" }),
    );
    const title = screen.getByRole("textbox", { name: "Workspace name" });
    await user.clear(title);
    await user.type(title, "Renamed course");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(
      await screen.findByRole("heading", { name: "Renamed course", level: 1 }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Delete workspace…" }));
    expect(requests.some((request) => request.method === "DELETE")).toBe(false);
    await user.click(screen.getByRole("button", { name: "Keep workspace" }));
    expect(
      screen.queryByRole("region", {
        name: "Confirm workspace deletion",
      }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Delete workspace…" }));
    await user.click(
      screen.getByRole("button", { name: /^Delete workspace$/ }),
    );
    expect(
      await screen.findByRole("heading", { name: "Your study starts here." }),
    ).toBeInTheDocument();
    expect(stored).toHaveLength(0);
  });
  it("has provider privacy disclosure and the existing MCP command", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: "Settings" }));
    expect(
      await screen.findByText("canvas-mcp --transport stdio"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Cloud providers receive your prompts/),
    ).toBeInTheDocument();
    expect(screen.getByText("Synthetic profile")).toBeInTheDocument();
  });
  it("supports browser history and collapsible panels", async () => {
    stored = [workspace];
    window.history.replaceState(
      null,
      "",
      `/workspace/${workspace.id}#session=synthetic-launch`,
    );
    const user = userEvent.setup();
    render(<App />);
    const sources = await screen.findByRole("button", { name: "Sources" });
    await user.click(sources);
    expect(sources).toHaveAttribute("aria-expanded", "false");
    window.history.replaceState(null, "", "/settings");
    window.dispatchEvent(new PopStateEvent("popstate"));
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Settings", level: 1 }),
      ).toBeInTheDocument(),
    );
  });
  it("gates the API UI on an authenticated local session", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        status: 401,
        ok: false,
        json: async () => ({
          error: { code: "session_required", message: "Expired" },
        }),
      }),
    );
    render(<App />);
    expect(
      await screen.findByText(/This session has ended/),
    ).toBeInTheDocument();
    expect(screen.queryByText("Canvas courses")).not.toBeInTheDocument();
  });
});
