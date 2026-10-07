import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LocalClients } from "./LocalClients";
import { ProviderSettings } from "./Providers";

const clients = {
  cli: [
    {
      kind: "codex",
      name: "Codex CLI",
      available: true,
      login_command: "codex login",
      mcp_command: "codex mcp add synthetic",
    },
    {
      kind: "claude_code",
      name: "Claude Code CLI",
      available: true,
      login_command: "claude auth login",
      mcp_command: "claude mcp add synthetic",
    },
  ],
  desktop: [
    { kind: "codex", name: "Codex app", available: true },
    { kind: "claude", name: "Claude Desktop", available: false },
  ],
  mcp_config: '{"mcpServers":{"hkust-canvas":{"command":"synthetic"}}}',
  can_open_login: true,
};
let requests: {
  path: string;
  method: string;
  body?: Record<string, unknown>;
}[];
let failure = false;
beforeEach(() => {
  requests = [];
  failure = false;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (path: string, options?: RequestInit) => {
      requests.push({
        path,
        method: options?.method || "GET",
        body: options?.body ? JSON.parse(String(options.body)) : undefined,
      });
      const data =
        path === "/api/local-clients"
          ? clients
          : path === "/api/providers"
            ? { providers: [] }
            : path.endsWith("/login")
              ? { opened: false, command: "claude auth login" }
              : path.endsWith("/connect")
                ? { connected: true, restart_required: true }
                : failure
                  ? {
                      error: {
                        code: "cli_auth",
                        message:
                          "Sign in to Claude Code CLI, then connect again.",
                      },
                    }
                  : { id: "synthetic-provider" };
      return {
        ok: !failure || !path.includes("/providers/local/"),
        status: failure ? 401 : 200,
        json: async () => data,
      } as Response;
    }),
  );
});

function row(name: string) {
  return within(
    screen.getByRole("heading", { name }).parentElement!.parentElement!,
  );
}

describe("Native provider and desktop setup", () => {
  it("uses an existing login without requesting an API key or sending an inference prompt", async () => {
    const connected = vi.fn(async () => {});
    render(<LocalClients onConnected={connected} />);
    await screen.findByRole("heading", { name: "Codex CLI" });
    await userEvent.click(
      row("Codex CLI").getByRole("button", { name: "Use existing login" }),
    );
    await waitFor(() => expect(connected).toHaveBeenCalledOnce());
    expect(requests.filter((r) => r.method === "POST")).toEqual([
      { path: "/api/providers/local/codex", method: "POST", body: undefined },
    ]);
    expect(screen.queryByLabelText(/API key/)).not.toBeInTheDocument();
  });
  it("gives a recoverable sign-in command when native auth is missing", async () => {
    failure = true;
    render(<LocalClients />);
    await screen.findByRole("heading", { name: "Claude Code CLI" });
    await userEvent.click(
      row("Claude Code CLI").getByRole("button", {
        name: "Use existing login",
      }),
    );
    expect(
      await screen.findByText(
        "Sign in to Claude Code CLI, then connect again.",
      ),
    ).toBeInTheDocument();
    await userEvent.click(
      row("Claude Code CLI").getByRole("button", { name: "Sign in" }),
    );
    expect(await screen.findByText("claude auth login")).toBeInTheDocument();
  });
  it("connects a detected desktop app only after a deliberate click", async () => {
    render(<LocalClients desktop />);
    await screen.findByRole("heading", { name: "Codex app" });
    expect(requests.every((r) => r.method === "GET")).toBe(true);
    expect(
      row("Claude Desktop").queryByRole("button", { name: "Connect Canvas" }),
    ).not.toBeInTheDocument();
    await userEvent.click(
      row("Codex app").getByRole("button", { name: "Connect Canvas" }),
    );
    expect(await screen.findByText(/Quit and reopen/)).toBeInTheDocument();
    expect(
      requests.some(
        (r) =>
          r.path === "/api/local-clients/codex/connect" && r.method === "POST",
      ),
    ).toBe(true);
  });
  it("hides API keys and tool switches for a native CLI provider", async () => {
    render(<ProviderSettings />);
    await screen.findByRole("heading", { name: "Codex CLI" });
    await userEvent.click(
      screen.getByRole("button", { name: "Add API or local server" }),
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Provider"),
      "claude_code",
    );
    expect(screen.queryByLabelText(/^API key/)).not.toBeInTheDocument();
    expect(
      screen.queryByRole("checkbox", { name: /native tool calling/ }),
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText(/Model identifier/)).toHaveValue("default");
  });
});
