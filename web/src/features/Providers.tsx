import { useEffect, useState } from "react";
import { Plus, Check, ExternalLink } from "lucide-react";
import { api } from "../api";
import { ErrorNotice, Loading } from "../components";
import type { Provider } from "../types";
import { LocalClients } from "./LocalClients";

export function ProviderSettings() {
  const [providers, setProviders] = useState<Provider[]>([]),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [tested, setTested] = useState<string | null>(null),
    [editing, setEditing] = useState<string | null>(null),
    [show, setShow] = useState(false),
    [deleting, setDeleting] = useState<string | null>(null);
  const [name, setName] = useState(""),
    [kind, setKind] = useState<Provider["kind"]>("openai"),
    [model, setModel] = useState(""),
    [url, setUrl] = useState("http://127.0.0.1:11434/v1"),
    [key, setKey] = useState(""),
    [removeKey, setRemoveKey] = useState(false),
    [tools, setTools] = useState(false),
    [streaming, setStreaming] = useState(true);
  const [structured, setStructured] = useState(false);
  async function load() {
    setProviders(
      (await api<{ providers: Provider[] }>("/api/providers")).providers,
    );
  }
  useEffect(() => {
    void load()
      .catch((p) => setError((p as Error).message))
      .finally(() => setLoading(false));
  }, []);
  function edit(provider?: Provider) {
    setEditing(provider?.id || null);
    setName(provider?.name || "");
    setKind(provider?.kind || "openai");
    setModel(provider?.model || "");
    setUrl(provider?.base_url || "http://127.0.0.1:11434/v1");
    setKey("");
    setRemoveKey(false);
    setTools(provider?.capabilities.native_tools || false);
    setStreaming(provider?.capabilities.streaming ?? true);
    setStructured(provider?.capabilities.structured_output ?? false);
    setShow(true);
    setError("");
  }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/api/providers", {
        method: "POST",
        body: {
          ...(editing ? { id: editing } : {}),
          name,
          kind,
          model,
          base_url: kind === "compatible" ? url : "",
          ...(key && kind !== "codex" && kind !== "claude_code"
            ? { api_key: key }
            : {}),
          remove_key:
            kind === "codex" || kind === "claude_code" ? false : removeKey,
          streaming,
          native_tools:
            kind === "codex" || kind === "claude_code" ? false : tools,
          structured_output: structured,
        },
      });
      setKey("");
      setShow(false);
      await load();
    } catch (p) {
      setKey("");
      setError((p as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function test(id: string) {
    setBusy(true);
    setError("");
    setTested(null);
    try {
      await api(`/api/providers/${id}/test`, { method: "POST" });
      setTested(id);
    } catch (p) {
      setError((p as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function remove(id: string) {
    setBusy(true);
    setError("");
    try {
      await api(`/api/providers/${id}`, { method: "DELETE" });
      setDeleting(null);
      await load();
    } catch (p) {
      setError((p as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <h2>Model providers</h2>
      <p>
        Use a signed-in CLI, an official API or a local model server. Select a
        connected provider in each workspace.
      </p>
      {error && <ErrorNotice message={error} />}
      {loading && <Loading>Loading providers…</Loading>}
      <LocalClients providers={providers} onConnected={load} />
      <div className="provider-list">
        {providers.map((p) => (
          <article className="provider-row" key={p.id}>
            <div>
              <h3>{p.name}</h3>
              <p>
                {p.model}{" "}
                <span className="provider-kind">
                  {p.kind === "compatible"
                    ? "Compatible API"
                    : p.kind === "openai"
                      ? "OpenAI"
                      : p.kind === "codex"
                        ? "Codex CLI"
                        : p.kind === "claude_code"
                          ? "Claude Code CLI"
                          : "Anthropic"}
                </span>
              </p>
              <small>
                {p.kind === "codex" || p.kind === "claude_code"
                  ? "Uses your CLI login"
                  : p.has_key
                    ? "Key saved in system credential store"
                    : p.kind === "compatible"
                      ? "No API key saved"
                      : "API key required"}{" "}
                ·{" "}
                {p.capabilities.native_tools
                  ? "Live tools enabled"
                  : "Chat without tools"}
              </small>
            </div>
            <div className="provider-actions">
              <button
                className="text-button"
                disabled={busy}
                onClick={() => void test(p.id)}
              >
                {tested === p.id ? (
                  <>
                    <Check size={14} />
                    Connected
                  </>
                ) : (
                  "Test connection"
                )}
              </button>
              <button
                className="text-button"
                disabled={busy}
                onClick={() => edit(p)}
              >
                Edit
              </button>
              <button
                className="text-button danger-text"
                disabled={busy}
                onClick={() => setDeleting(p.id)}
              >
                Remove
              </button>
            </div>
            {deleting === p.id && (
              <div className="inline-confirm">
                <p>
                  Remove this provider configuration? Saved conversations and
                  study materials stay local.
                </p>
                <button
                  className="button danger small"
                  disabled={busy}
                  onClick={() => void remove(p.id)}
                >
                  Remove provider
                </button>
                <button
                  className="text-button"
                  onClick={() => setDeleting(null)}
                >
                  Keep provider
                </button>
              </div>
            )}
          </article>
        ))}
      </div>
      {!show ? (
        <button className="button secondary" onClick={() => edit()}>
          <Plus size={16} />
          Add API or local server
        </button>
      ) : (
        <form className="provider-form" onSubmit={(e) => void save(e)}>
          <div className="form-row">
            <label>
              Name
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                maxLength={80}
                placeholder="My study model"
              />
            </label>
            <label>
              Provider
              <select
                value={kind}
                disabled={!!editing}
                onChange={(e) => {
                  const value = e.target.value as Provider["kind"];
                  setKind(value);
                  setKey("");
                  if (value === "codex" || value === "claude_code") {
                    setModel("default");
                    if (!name)
                      setName(
                        value === "codex" ? "Codex CLI" : "Claude Code CLI",
                      );
                    setTools(false);
                    setStructured(true);
                  }
                }}
              >
                <option value="openai">OpenAI API</option>
                <option value="anthropic">Anthropic API</option>
                <option value="compatible">OpenAI-compatible / local</option>
                <option value="codex">Codex CLI (existing login)</option>
                <option value="claude_code">
                  Claude Code CLI (existing login)
                </option>
              </select>
            </label>
          </div>
          <label>
            Model identifier{" "}
            {kind === "codex" || kind === "claude_code" ? '(or "default")' : ""}
            <input
              required
              maxLength={160}
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="Enter a model available on your account or server"
            />
          </label>
          {kind === "compatible" && (
            <>
              <label>
                API base URL
                <input
                  type="url"
                  value={url}
                  required
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="http://127.0.0.1:11434/v1"
                />
              </label>
              <p className="muted">
                Ollama: http://127.0.0.1:11434/v1 · LM Studio:
                http://127.0.0.1:1234/v1. Start your local server and load a
                model first.
              </p>
            </>
          )}
          {kind !== "codex" && kind !== "claude_code" && (
            <label>
              {editing
                ? "Replace API key (leave blank to keep it)"
                : `API key${kind === "compatible" ? " (optional for local servers)" : ""}`}
              <input
                type="password"
                autoComplete="new-password"
                spellCheck={false}
                value={key}
                maxLength={1000}
                onChange={(e) => {
                  setKey(e.target.value);
                  setRemoveKey(false);
                }}
              />
            </label>
          )}
          {editing && kind !== "codex" && kind !== "claude_code" && (
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={removeKey}
                onChange={(e) => {
                  setRemoveKey(e.target.checked);
                  setKey("");
                }}
              />
              Remove the saved key
            </label>
          )}
          {kind !== "codex" && kind !== "claude_code" ? (
            <fieldset className="provider-capabilities">
              <legend>Model support</legend>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={streaming}
                  onChange={(e) => setStreaming(e.target.checked)}
                />
                Stream responses
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={tools}
                  onChange={(e) => setTools(e.target.checked)}
                />
                This model supports native tool calling
              </label>
              <p className="muted">
                Enable tools only if the selected model supports them. Without
                tools, use explicit Live Canvas actions. Study Studio validates
                generated JSON for either mode.
              </p>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={structured}
                  onChange={(e) => setStructured(e.target.checked)}
                />
                This model supports native JSON Schema output
              </label>
            </fieldset>
          ) : (
            <p className="muted">
              Uses the native CLI login. Streaming and validated study materials
              are enabled. Use Live Canvas actions for current Canvas checks and
              write previews.
            </p>
          )}
          <div className="form-actions">
            <button className="button primary" disabled={busy}>
              {busy ? "Saving…" : "Save provider"}
            </button>
            <button
              type="button"
              className="button secondary"
              onClick={() => {
                setShow(false);
                setKey("");
              }}
            >
              Cancel
            </button>
          </div>
        </form>
      )}
      <p className="provider-disclosure">
        Cloud providers receive your prompts, conversation history and retrieved
        excerpts from selected sources only when you send or generate. Local
        endpoints receive the same context. A connection test sends only a short
        test prompt and uses the provider's billing or account quota.
      </p>
      <p className="muted">
        A ChatGPT or Claude subscription is separate from API billing. You can
        use the CLI's existing login here, or use an MCP-capable desktop client.
      </p>
      <div className="provider-docs">
        <a
          href="https://platform.openai.com/api-keys"
          target="_blank"
          rel="noopener noreferrer"
        >
          OpenAI API keys <ExternalLink size={13} />
        </a>
        <a
          href="https://platform.claude.com/settings/keys"
          target="_blank"
          rel="noopener noreferrer"
        >
          Anthropic API keys <ExternalLink size={13} />
        </a>
      </div>
    </>
  );
}
