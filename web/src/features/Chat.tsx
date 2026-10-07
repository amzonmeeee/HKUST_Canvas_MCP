import { useEffect, useRef, useState } from "react";
import {
  Send,
  Square,
  Plus,
  MessageSquare,
  Bookmark,
  Trash2,
} from "lucide-react";
import { api, stream } from "../api";
import { ErrorNotice, Loading } from "../components";
import { StudyMarkdown, CitationList } from "./StudyContent";
import { LiveActions, WritePreview, actionLabel } from "./Actions";
import type {
  Citation,
  Conversation,
  Message,
  Preview,
  Provider,
  Workspace,
} from "../types";

export function ChatPanel({
  workspace,
  sourceIds,
  providerId,
  setProviderId,
  openCitation,
  notesChanged,
  navigate,
}: {
  workspace: Workspace;
  sourceIds: string[];
  providerId: string;
  setProviderId: (id: string) => void;
  openCitation: (c: Citation) => void;
  notesChanged: () => void;
  navigate: (path: string) => void;
}) {
  const base = `/api/workspaces/${workspace.id}`;
  const [providers, setProviders] = useState<Provider[]>([]),
    [conversations, setConversations] = useState<Conversation[]>([]),
    [conversationId, setConversationId] = useState(""),
    [messages, setMessages] = useState<Message[]>([]),
    [text, setText] = useState(""),
    [error, setError] = useState(""),
    [warning, setWarning] = useState(""),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true),
    [live, setLive] = useState(false),
    [activity, setActivity] = useState(""),
    [previews, setPreviews] = useState<Preview[]>([]),
    [deleting, setDeleting] = useState(false),
    [retrieved, setRetrieved] = useState<Citation[]>([]),
    [saved, setSaved] = useState<string[]>([]);
  const [sendShortcut, setSendShortcut] = useState<"enter" | "mod-enter">(
    () => {
      try {
        return localStorage.getItem("canvas-workbench.send-shortcut") ===
          "enter"
          ? "enter"
          : "mod-enter";
      } catch {
        return "mod-enter";
      }
    },
  );
  useEffect(() => {
    try {
      localStorage.setItem("canvas-workbench.send-shortcut", sendShortcut);
    } catch {
      /* Optional preference. */
    }
  }, [sendShortcut]);
  const controller = useRef<AbortController | null>(null),
    end = useRef<HTMLDivElement>(null);
  const provider = providers.find((p) => p.id === providerId);
  async function refresh() {
    setConversations(
      (await api<{ conversations: Conversation[] }>(`${base}/conversations`))
        .conversations,
    );
  }
  useEffect(() => {
    void (async () => {
      try {
        const [p, c, a] = await Promise.all([
          api<{ providers: Provider[] }>("/api/providers"),
          api<{ conversations: Conversation[] }>(`${base}/conversations`),
          api<{ previews: Preview[] }>(`${base}/actions`),
        ]);
        setProviders(p.providers);
        setConversations(c.conversations);
        setPreviews(a.previews);
        if (!providerId && p.providers[0]) setProviderId(p.providers[0].id);
      } catch (p) {
        setError((p as Error).message);
      } finally {
        setLoading(false);
      }
    })();
    return () => controller.current?.abort();
  }, [workspace.id]);
  useEffect(() => {
    if (!provider?.capabilities.native_tools) setLive(false);
  }, [providerId, providers]);
  useEffect(() => {
    if (busy)
      end.current?.scrollIntoView({ block: "nearest", behavior: "instant" });
  }, [messages.length, busy]);
  async function open(id: string) {
    setConversationId(id);
    setDeleting(false);
    setError("");
    setWarning("");
    setRetrieved([]);
    if (!id) {
      setMessages([]);
      return;
    }
    try {
      const c = await api<Conversation>(`${base}/conversations/${id}`);
      setMessages(c.messages || []);
    } catch (p) {
      setError((p as Error).message);
    }
  }
  async function send(event: React.FormEvent) {
    event.preventDefault();
    if (busy || !text.trim() || !providerId) return;
    const prompt = text.trim();
    setText("");
    setBusy(true);
    setError("");
    setWarning("");
    setRetrieved([]);
    setActivity("");
    const abort = new AbortController();
    controller.current = abort;
    const assistantId = "streaming-answer";
    let activeId = conversationId;
    setMessages((previous) => [
      ...previous,
      {
        id: "current-user",
        role: "user",
        content: prompt,
        status: "complete",
        citations: [],
        provider_id: null,
        model: null,
      },
      {
        id: assistantId,
        role: "assistant",
        content: "",
        status: "streaming",
        citations: [],
        provider_id: providerId,
        model: provider?.model || null,
      },
    ]);
    try {
      await stream(
        `${base}/chat`,
        {
          message: prompt,
          provider_id: providerId,
          source_ids: sourceIds,
          ...(conversationId ? { conversation_id: conversationId } : {}),
          live_tools: live,
        },
        (event) => {
          if (event.type === "conversation") {
            activeId = String(event.conversation_id);
            setConversationId(activeId);
          }
          if (event.type === "text_delta")
            setMessages((previous) =>
              previous.map((m) =>
                m.id === assistantId
                  ? { ...m, content: m.content + String(event.text) }
                  : m,
              ),
            );
          if (event.type === "context")
            setRetrieved(event.chunks as Citation[]);
          if (event.type === "citation")
            setMessages((previous) =>
              previous.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      citations: [...m.citations, event.citation as Citation],
                    }
                  : m,
              ),
            );
          if (event.type === "message_end")
            setMessages((previous) =>
              previous.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      content: String(event.content),
                      status: "complete",
                      citations: event.citations as Citation[],
                    }
                  : m,
              ),
            );
          if (event.type === "error") setError(String(event.message));
          if (event.type === "warning") setWarning(String(event.message));
          if (event.type === "tool_activity")
            setActivity(`${actionLabel(String(event.name))} · ${event.status}`);
          if (event.type === "write_preview")
            setPreviews((previous) => [...previous, event.preview as Preview]);
        },
        abort.signal,
      );
    } catch (p) {
      if ((p as Error).name !== "AbortError") setError((p as Error).message);
      else setWarning("Response stopped. Partial text is saved.");
    } finally {
      setBusy(false);
      setActivity("");
      controller.current = null;
      await refresh().catch(() => {});
      if (activeId) {
        try {
          const result = await api<Conversation>(
            `${base}/conversations/${activeId}`,
          );
          setMessages(result.messages || []);
        } catch {
          /* Keep the partial UI answer if the local server disconnected. */
        }
      }
    }
  }
  async function saveMessage(m: Message) {
    try {
      await api(`${base}/notes`, {
        method: "POST",
        body: {
          title:
            messages.find((x) => x.role === "user")?.content.slice(0, 120) ||
            "Saved answer",
          content: "",
          message_id: m.id,
        },
      });
      setSaved([...saved, m.id]);
      notesChanged();
    } catch (p) {
      setError((p as Error).message);
    }
  }
  async function remove() {
    try {
      await api(`${base}/conversations/${conversationId}`, {
        method: "DELETE",
      });
      await open("");
      await refresh();
    } catch (p) {
      setError((p as Error).message);
    }
  }
  return (
    <div className="chat-content">
      <div className="chat-toolbar">
        <div className="chat-controls">
          <label>
            <span>Provider</span>
            <select
              value={providerId}
              disabled={busy}
              onChange={(e) => setProviderId(e.target.value)}
            >
              <option value="">Choose a provider</option>
              {providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} · {p.model}
                </option>
              ))}
            </select>
          </label>
          <button
            className="icon-button"
            aria-label="New conversation"
            disabled={busy}
            onClick={() => void open("")}
          >
            <Plus size={18} />
          </button>
        </div>
        {conversations.length > 0 && (
          <div className="conversation-controls">
            <label htmlFor="conversation-choice">History</label>
            <select
              id="conversation-choice"
              aria-label="Conversation history"
              value={conversationId}
              disabled={busy}
              onChange={(e) => void open(e.target.value)}
            >
              <option value="">New conversation</option>
              {conversations.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
            </select>
            {conversationId && (
              <button
                className="icon-button"
                disabled={busy}
                aria-label="Delete conversation"
                onClick={() => setDeleting(!deleting)}
              >
                <Trash2 size={16} />
              </button>
            )}
          </div>
        )}
      </div>
      {deleting && (
        <div className="inline-confirm">
          <p>Delete this conversation?</p>
          <button className="button danger small" onClick={() => void remove()}>
            Delete conversation
          </button>
          <button className="text-button" onClick={() => setDeleting(false)}>
            Keep it
          </button>
        </div>
      )}
      {error && <ErrorNotice message={error} />}{" "}
      {warning && (
        <p className="inline-warning" role="status">
          {warning}
        </p>
      )}
      <div
        className="messages"
        aria-label="Conversation messages"
        aria-busy={busy}
      >
        {loading && <Loading>Loading conversations…</Loading>}
        {!loading && !messages.length && (
          <div className="chat-empty">
            <MessageSquare size={28} />
            <h3>Ask with your materials beside you.</h3>
            <p>
              Select ready sources, choose a provider, and ask a question.
              Answers cite the excerpts they use.
            </p>
            {!providers.length && (
              <button
                className="button secondary"
                onClick={() => navigate("/settings")}
              >
                Set up a provider
              </button>
            )}
          </div>
        )}
        {messages.map((m) => (
          <article key={m.id} className={`chat-message ${m.role}`}>
            <div className="message-label">
              <strong>{m.role === "user" ? "You" : "Study assistant"}</strong>
              {m.role === "assistant" && (
                <small>
                  {m.model}
                  {m.status !== "complete" && ` · ${m.status}`}
                </small>
              )}
            </div>
            {m.role === "user" ? (
              <p className="user-prompt">{m.content}</p>
            ) : (
              <>
                <StudyMarkdown
                  text={
                    m.content ||
                    (busy
                      ? "Reading the selected context…"
                      : "No text was generated.")
                  }
                  citations={m.citations}
                  openCitation={openCitation}
                />
                <CitationList citations={m.citations} open={openCitation} />
                {m.id !== "streaming-answer" && (
                  <button
                    className="text-button save-answer"
                    onClick={() => void saveMessage(m)}
                    disabled={saved.includes(m.id)}
                  >
                    <Bookmark size={14} />
                    {saved.includes(m.id) ? "Saved to notes" : "Save to notes"}
                  </button>
                )}
              </>
            )}
          </article>
        ))}
        <div ref={end} />
      </div>
      {activity && (
        <p className="tool-activity" role="status">
          {activity}
        </p>
      )}
      {retrieved.length > 0 && (
        <details className="retrieved-context">
          <summary>{retrieved.length} retrieved excerpts</summary>
          <CitationList citations={retrieved} open={openCitation} />
        </details>
      )}
      <form className="chat-composer" onSubmit={(e) => void send(e)}>
        <label className="visually-hidden" htmlFor="chat-prompt">
          Ask a study question
        </label>
        <textarea
          id="chat-prompt"
          value={text}
          rows={3}
          maxLength={12000}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(event) => {
            if (
              event.key !== "Enter" ||
              event.nativeEvent.isComposing ||
              event.keyCode === 229 ||
              event.repeat
            )
              return;
            const modified = event.metaKey || event.ctrlKey;
            const shouldSend =
              sendShortcut === "enter"
                ? !modified && !event.shiftKey && !event.altKey
                : modified && !event.shiftKey && !event.altKey;
            if (shouldSend) {
              event.preventDefault();
              event.currentTarget.form?.requestSubmit();
            } else if (modified) {
              event.preventDefault();
              const input = event.currentTarget,
                start = input.selectionStart,
                finish = input.selectionEnd;
              setText(text.slice(0, start) + "\n" + text.slice(finish));
              requestAnimationFrame(() =>
                input.setSelectionRange(start + 1, start + 1),
              );
            }
          }}
          placeholder="Ask about selected sources, or request a live Canvas check…"
          disabled={busy}
        />
        <div className="composer-footer">
          <div className="composer-options">
            <span>{sourceIds.length} sources selected</span>
            <label>
              Send with{" "}
              <select
                aria-label="Send shortcut"
                value={sendShortcut}
                onChange={(event) =>
                  setSendShortcut(event.target.value as "enter" | "mod-enter")
                }
              >
                <option value="enter">Return</option>
                <option value="mod-enter">⌘ / Ctrl + Return</option>
              </select>
            </label>
            <small>
              {sendShortcut === "enter"
                ? "⌘ / Ctrl + Return or Shift + Return for a new line"
                : "Return for a new line"}
            </small>
          </div>
          {busy ? (
            <button
              type="button"
              className="button secondary small"
              onClick={() => controller.current?.abort()}
            >
              <Square size={13} />
              Stop
            </button>
          ) : (
            <button
              className="button primary small"
              disabled={!providerId || !text.trim()}
            >
              <Send size={14} />
              Send
            </button>
          )}
        </div>
        <label className="checkbox-label live-toggle">
          <input
            type="checkbox"
            checked={live}
            disabled={busy || !provider?.capabilities.native_tools}
            onChange={(e) => setLive(e.target.checked)}
          />
          Allow live Canvas tools for this conversation
        </label>
        <p className="chat-disclosure">
          {provider
            ? `Sending uses ${provider.name} (${provider.model}) and shares your prompt, recent history and retrieved selected-source excerpts${live ? ", plus requested live Canvas results" : ""}.`
            : "Choose a provider in Settings to chat. Live Canvas actions below do not need a model."}
        </p>
      </form>
      {previews.map((p) => (
        <WritePreview
          key={p.id}
          workspaceId={workspace.id}
          preview={p}
          onFinished={() => {}}
        />
      ))}
      <LiveActions
        workspace={workspace}
        onPreview={(p) => setPreviews((previous) => [...previous, p])}
      />
    </div>
  );
}
