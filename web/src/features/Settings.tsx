import { useEffect, useState } from "react";
import { Copy, Check, ArrowUpRight } from "lucide-react";
import { api } from "../api";
import { CanvasLink, ErrorNotice, Loading } from "../components";
import type { Settings } from "../types";
import { ProviderSettings } from "./Providers";
import { CanvasConfiguration } from "./CanvasConfiguration";
import { LocalClients } from "./LocalClients";

export function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  async function load() {
    setError("");
    try {
      setSettings(await api<Settings>("/api/settings"));
    } catch (problem) {
      setError((problem as Error).message);
    }
  }
  useEffect(() => {
    void load();
  }, []);
  async function copy() {
    try {
      await navigator.clipboard.writeText(settings!.mcp_command);
      setCopied(true);
    } catch {
      setError(
        "Copy is unavailable in this browser. Select and copy the command below.",
      );
    }
  }
  return (
    <>
      <header className="page-header">
        <div>
          <h1>Settings</h1>
          <p>One Canvas connection. Your choice of client.</p>
        </div>
      </header>
      {error && <ErrorNotice message={error} retry={() => void load()} />}
      {!settings ? (
        !error && <Loading>Loading settings…</Loading>
      ) : (
        <div className="settings-content">
          <section className="settings-section">
            <h2>Canvas connection</h2>
            <p>
              The workbench shares the Chrome session and profile selection used
              by the Canvas CLI and MCP server.
            </p>
            <CanvasConfiguration onChanged={() => void load()} />
            <CanvasLink />
            <p className="muted">
              Sign in through Chrome if your session expires, then refresh the
              dashboard.
            </p>
          </section>
          <section className="settings-section">
            <ProviderSettings />
          </section>
          <section className="settings-section">
            <h2>MCP clients</h2>
            <LocalClients desktop />
            <p>
              The existing MCP server continues to work with Claude, Codex and
              other MCP-capable clients.
            </p>
            <div className="command-field">
              <code>{settings.mcp_command}</code>
              <button
                className="icon-button"
                aria-label={copied ? "Command copied" : "Copy MCP command"}
                onClick={() => void copy()}
              >
                {copied ? <Check size={18} /> : <Copy size={18} />}
              </button>
            </div>
            <p className="muted">
              Configure this command in your client's MCP settings. Run the
              client with access to the same Chrome profile.
            </p>
            <a
              className="external-link"
              href="https://github.com/amzonmeeee/HKUST_Canvas_MCP#install"
              target="_blank"
              rel="noopener noreferrer"
            >
              Project setup
              <ArrowUpRight size={15} aria-hidden="true" />
            </a>
          </section>
          <section className="settings-section">
            <h2>Local storage & privacy</h2>
            <p>
              Workspaces, indexed sources, conversations, study materials and
              notes are saved on this computer, in your operating system's
              application-data directory outside this repository.
            </p>
            <dl className="settings-facts">
              <div>
                <dt>Database schema</dt>
                <dd>Version {settings.schema_version}</dd>
              </div>
              <div>
                <dt>Server access</dt>
                <dd>Loopback only · local session protected</dd>
              </div>
            </dl>
            <p className="muted">
              Canvas cookies stay in the Python backend. They are never exposed
              to this page or stored in the workspace database.
            </p>
          </section>
        </div>
      )}
    </>
  );
}
