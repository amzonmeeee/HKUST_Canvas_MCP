import { useEffect, useState } from "react";
import { Check, Copy, ExternalLink, RefreshCw } from "lucide-react";
import { api } from "../api";
import { ErrorNotice } from "../components";
import type { Provider } from "../types";

type CLI = {
  kind: "codex" | "claude_code";
  name: string;
  available: boolean;
  login_command: string;
  mcp_command: string;
};
type Clients = {
  cli: CLI[];
  desktop: { kind: "codex" | "claude"; name: string; available: boolean }[];
  mcp_config: string;
  can_open_login: boolean;
};
const docs = {
  codex: "https://learn.chatgpt.com/docs/extend/mcp",
  claude:
    "https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop",
};

export function LocalClients({
  desktop = false,
  providers = [],
  onConnected,
}: {
  desktop?: boolean;
  providers?: Provider[];
  onConnected?: () => Promise<void>;
}) {
  const [clients, setClients] = useState<Clients | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [copied, setCopied] = useState("");
  const [notice, setNotice] = useState("");
  const [setup, setSetup] = useState("");
  async function load() {
    setError("");
    try {
      setClients(await api<Clients>("/api/local-clients"));
    } catch (problem) {
      setError((problem as Error).message);
    }
  }
  useEffect(() => {
    void load();
  }, []);
  async function copy(value: string, id: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(id);
    } catch {
      setSetup(value);
      setError("Select and copy the setup text below.");
    }
  }
  async function action(path: string, kind: string, connected = false) {
    setBusy(kind);
    setError("");
    setNotice("");
    try {
      const result = await api<{
        opened?: boolean;
        command?: string;
        restart_required?: boolean;
      }>(path, { method: "POST" });
      if (connected) {
        await onConnected?.();
        setNotice(
          "Provider connected. Return to your workspace and select it for chat or Study Studio.",
        );
      } else if (result.command) {
        setSetup(result.command);
        setNotice(
          result.opened
            ? "Finish signing in in Terminal, then choose Use existing login."
            : "Run this sign-in command in your terminal, then choose Use existing login.",
        );
      } else if (result.restart_required) {
        setNotice(
          "Canvas MCP connected. Quit and reopen the desktop app to load the connection. Your other MCP entries are preserved.",
        );
      }
    } catch (problem) {
      setError((problem as Error).message);
    } finally {
      setBusy("");
    }
  }
  return (
    <div className="local-clients">
      {!desktop && (
        <>
          <h3>Use your existing login</h3>
          <p>
            Connect Codex or Claude Code to chat and generate study materials
            here. No API key to paste. Requests use your CLI account and its
            usage limits.
          </p>
        </>
      )}
      {desktop && (
        <p>
          Use Canvas from the Codex app or Claude Desktop through MCP. Chat runs
          in the desktop app; the providers above answer inside this workbench.
        </p>
      )}
      {error && <ErrorNotice message={error} retry={() => void load()} />}
      {notice && <p role="status">{notice}</p>}
      {!clients && !error && <p role="status">Checking available clients…</p>}
      {clients &&
        (desktop ? clients.desktop : clients.cli).map((client) => {
          const kind = client.kind;
          const saved = providers.some((p) => p.kind === kind);
          const cli = clients!.cli.find(
            (c) => c.kind === (kind === "claude" ? "claude_code" : kind),
          );
          return (
            <div className="local-client-row" key={kind}>
              <div>
                <h3>{client.name}</h3>
                <small>
                  {client.available
                    ? desktop
                      ? "App found on this computer"
                      : saved
                        ? "Provider connected"
                        : "CLI found on this computer"
                    : desktop
                      ? "App not detected"
                      : "CLI not detected"}
                </small>
              </div>
              <div className="provider-actions">
                {desktop ? (
                  <>
                    <button
                      className="text-button"
                      onClick={() => {
                        const text =
                          kind === "claude"
                            ? clients!.mcp_config
                            : cli?.mcp_command || "";
                        setSetup(text);
                        void copy(text, kind);
                      }}
                    >
                      {copied === kind ? (
                        <>
                          <Check size={14} /> Copied
                        </>
                      ) : (
                        <>
                          <Copy size={14} /> Copy MCP setup
                        </>
                      )}
                    </button>
                    {client.available && (
                      <>
                        <button
                          className="button secondary small"
                          disabled={!!busy}
                          onClick={() =>
                            void action(
                              `/api/local-clients/${kind}/connect`,
                              kind,
                            )
                          }
                        >
                          {busy === kind ? "Connecting…" : "Connect Canvas"}
                        </button>
                        <button
                          className="text-button"
                          disabled={!!busy}
                          onClick={() =>
                            void action(`/api/local-clients/${kind}/open`, kind)
                          }
                        >
                          Open app
                        </button>
                      </>
                    )}
                    <a
                      className="external-link"
                      href={docs[kind as "codex" | "claude"]}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Setup guide <ExternalLink size={13} />
                    </a>
                  </>
                ) : (
                  <>
                    {client.available ? (
                      <>
                        <button
                          className="text-button"
                          disabled={!!busy}
                          onClick={() =>
                            void action(
                              `/api/local-clients/${kind}/login`,
                              kind,
                            )
                          }
                        >
                          Sign in
                        </button>
                        <button
                          className="button secondary small"
                          disabled={!!busy || saved}
                          onClick={() =>
                            void action(
                              `/api/providers/local/${kind}`,
                              kind,
                              true,
                            )
                          }
                        >
                          {busy === kind
                            ? "Connecting…"
                            : saved
                              ? "Connected"
                              : "Use existing login"}
                        </button>
                      </>
                    ) : (
                      <a
                        className="external-link"
                        href={
                          kind === "codex"
                            ? "https://learn.chatgpt.com/docs/cli"
                            : "https://code.claude.com/docs/en/setup"
                        }
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        Installation guide <ExternalLink size={13} />
                      </a>
                    )}
                  </>
                )}
              </div>
            </div>
          );
        })}
      <button
        className="text-button"
        disabled={!!busy}
        onClick={() => void load()}
      >
        <RefreshCw size={14} /> Refresh availability
      </button>
      {desktop && (
        <p className="muted">
          For Codex, run the copied setup command in Terminal, then reopen the
          app. For Claude Desktop, open Settings → Developer → Edit Config and
          add the copied hkust-canvas entry under mcpServers, keeping existing
          entries. Restart Claude Desktop.
        </p>
      )}
      {setup && (
        <details open className="client-setup">
          <summary>Setup text</summary>
          <pre tabIndex={0}>{setup}</pre>
        </details>
      )}
    </div>
  );
}
