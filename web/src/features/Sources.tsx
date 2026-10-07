import { useEffect, useRef, useState } from "react";
import {
  Check,
  RefreshCw,
  Upload,
  Plus,
  FileText,
  Trash2,
  BookOpen,
  Layers,
  MessageSquare,
  ClipboardList,
  Megaphone,
  Link,
} from "lucide-react";
import { api, upload } from "../api";
import { ErrorNotice, Loading } from "../components";
import type { Source, Workspace } from "../types";

export function SourcesPanel({
  workspace,
  selected,
  setSelected,
  openSource,
}: {
  workspace: Workspace;
  selected: string[];
  setSelected: (ids: string[]) => void;
  openSource: (id: string) => void;
}) {
  const base = `/api/workspaces/${workspace.id}/sources`;
  const [sources, setSources] = useState<Source[]>([]),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [warnings, setWarnings] = useState<string[]>([]),
    [manual, setManual] = useState(false),
    [title, setTitle] = useState(""),
    [text, setText] = useState(""),
    [filter, setFilter] = useState(""),
    [removing, setRemoving] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null),
    alive = useRef(true);
  async function load() {
    const result = await api<{ sources: Source[] }>(base);
    if (alive.current) setSources(result.sources);
  }
  useEffect(() => {
    alive.current = true;
    setLoading(true);
    void load()
      .catch((p) => setError((p as Error).message))
      .finally(() => setLoading(false));
    return () => {
      alive.current = false;
    };
  }, [workspace.id]);
  async function operation(action: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    setWarnings([]);
    // Poll status during explicit operations; regular page loads never start a sync.
    const poll = window.setInterval(() => void load().catch(() => {}), 1500);
    try {
      await action();
      await load();
    } catch (p) {
      setError((p as Error).message);
    } finally {
      window.clearInterval(poll);
      setBusy(false);
    }
  }
  async function sync(all = false) {
    await operation(async () => {
      const result = await api<{ warnings?: { message: string }[] }>(
        all ? `${base}/sync-course` : `${base}/sync`,
        { method: "POST", body: all ? undefined : { source_ids: selected } },
      );
      setWarnings(result.warnings?.map((w) => w.message) || []);
    });
  }
  async function pick(file: File) {
    if (file.size > 25 * 1024 * 1024) {
      setError("Choose a file of at most 25 MB.");
      return;
    }
    await operation(async () => {
      const source = await upload<Source>(`${base}/upload`, file);
      if (source.status === "ready")
        setSelected([...new Set([...selected, source.id])]);
    });
  }
  async function addText(event: React.FormEvent) {
    event.preventDefault();
    await operation(async () => {
      const source = await api<Source>(`${base}/text`, {
        method: "POST",
        body: { title, content: text },
      });
      if (source.status === "ready")
        setSelected([...new Set([...selected, source.id])]);
      setManual(false);
      setTitle("");
      setText("");
    });
  }
  const visible = sources.filter((s) =>
    s.title.toLowerCase().includes(filter.toLowerCase()),
  );
  const readySelected = sources.filter(
    (s) => selected.includes(s.id) && s.status === "ready",
  ).length;
  const groups = [...new Set(visible.map((s) => s.kind))];
  function toggleGroup(members: Source[]) {
    const ids = members
      .filter((source) => source.status !== "external_reference")
      .map((source) => source.id);
    const all = ids.length > 0 && ids.every((id) => selected.includes(id));
    setSelected(
      all
        ? selected.filter((id) => !ids.includes(id))
        : [...new Set([...selected, ...ids])],
    );
  }
  function toggle(id: string) {
    const source = sources.find((s) => s.id === id);
    if (source?.kind === "module") {
      const keys = source.metadata.items?.map((i) => i.source_key) || [];
      const members = [
        id,
        ...sources
          .filter(
            (s) =>
              keys.includes(s.source_key) && s.status !== "external_reference",
          )
          .map((s) => s.id),
      ];
      setSelected(
        selected.includes(id)
          ? selected.filter((s) => !members.includes(s))
          : [...new Set([...selected, ...members])],
      );
      return;
    }
    setSelected(
      selected.includes(id)
        ? selected.filter((s) => s !== id)
        : [...selected, id],
    );
  }
  function icon(kind: string) {
    const Icon =
      (
        {
          syllabus: BookOpen,
          module: Layers,
          assignment: ClipboardList,
          announcement: Megaphone,
          discussion: MessageSquare,
          external: Link,
        } as Record<string, typeof FileText>
      )[kind] || FileText;
    return <Icon size={13} aria-hidden="true" />;
  }
  return (
    <div className="sources-content">
      <div className="source-toolbar">
        {workspace.canvas_course_id && (
          <>
            <button
              className="button secondary small"
              disabled={busy}
              onClick={() =>
                void operation(async () => {
                  const r = await api<{ warnings: { message: string }[] }>(
                    `${base}/inventory`,
                    { method: "POST" },
                  );
                  setWarnings(r.warnings.map((w) => w.message));
                })
              }
            >
              <RefreshCw size={15} />
              Find course sources
            </button>
            <button
              className="text-button"
              disabled={busy}
              onClick={() => void sync(true)}
            >
              Sync course
            </button>
          </>
        )}
        <input
          ref={input}
          type="file"
          className="visually-hidden"
          aria-label="Source file"
          accept=".txt,.md,.html,.htm,.pdf,.docx,.pptx,.vtt,.srt"
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (file) void pick(file);
          }}
        />
        <button
          className="text-button"
          disabled={busy}
          onClick={() => input.current?.click()}
        >
          <Upload size={15} />
          Upload
        </button>
        <button
          className="text-button"
          disabled={busy}
          onClick={() => setManual(!manual)}
        >
          <Plus size={15} />
          Add text
        </button>
      </div>
      {error && <ErrorNotice message={error} />}
      {warnings.length > 0 && (
        <div className="source-warnings" role="status">
          {warnings.map((w, i) => (
            <p key={i}>{w}</p>
          ))}
        </div>
      )}
      {manual && (
        <form className="compact-form" onSubmit={(e) => void addText(e)}>
          <label>
            Source title
            <input
              value={title}
              maxLength={160}
              required
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>
          <label>
            Text or Markdown
            <textarea
              value={text}
              maxLength={200000}
              rows={8}
              required
              onChange={(e) => setText(e.target.value)}
            />
          </label>
          <button className="button primary small" disabled={busy}>
            Save source
          </button>
        </form>
      )}
      {loading ? (
        <Loading>Loading sources…</Loading>
      ) : sources.length === 0 ? (
        <div className="panel-empty">
          <FileText size={25} />
          <h3>Start with your materials.</h3>
          <p>
            {workspace.canvas_course_id
              ? "Find Canvas sources, then select what to sync. You can also upload your own documents."
              : "Upload a PDF, Word document, slides, text or captions. Each stays in this workspace."}
          </p>
        </div>
      ) : (
        <>
          <label className="source-filter">
            <span className="visually-hidden">Filter sources</span>
            <input
              placeholder="Find a source…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </label>
          <div className="source-selection">
            <span>
              {selected.length} selected · {readySelected} ready
            </span>
            <button
              className="text-button"
              onClick={() =>
                setSelected(
                  sources.filter((s) => s.status === "ready").map((s) => s.id),
                )
              }
            >
              Select ready
            </button>
            <button
              className="text-button"
              onClick={() =>
                setSelected(
                  sources
                    .filter((s) => s.status !== "external_reference")
                    .map((s) => s.id),
                )
              }
            >
              Select all
            </button>
            <button className="text-button" onClick={() => setSelected([])}>
              Clear
            </button>
          </div>
          <button
            className="button secondary small sync-selected"
            disabled={busy || !selected.length}
            onClick={() => void sync()}
          >
            <RefreshCw size={15} className={busy ? "spinning" : ""} />
            {busy ? "Syncing…" : "Sync selected"}
          </button>
          <div className="source-groups">
            {groups.map((kind) => (
              <details className="source-group" key={kind} open>
                <summary>
                  {kind === "upload"
                    ? "Your uploads"
                    : kind[0].toUpperCase() + kind.slice(1) + "s"}
                  <span>{visible.filter((s) => s.kind === kind).length}</span>
                </summary>
                <button
                  className="text-button select-category"
                  disabled={
                    !visible.some(
                      (s) =>
                        s.kind === kind && s.status !== "external_reference",
                    )
                  }
                  onClick={() =>
                    toggleGroup(visible.filter((s) => s.kind === kind))
                  }
                >
                  {visible
                    .filter(
                      (s) =>
                        s.kind === kind && s.status !== "external_reference",
                    )
                    .every((s) => selected.includes(s.id))
                    ? "Clear category"
                    : "Select category"}
                  <span className="visually-hidden"> {kind}</span>
                </button>
                {visible
                  .filter((s) => s.kind === kind)
                  .map((s) => (
                    <div className={`source-row source-${s.status}`} key={s.id}>
                      <input
                        aria-label={`Select ${s.title}`}
                        type="checkbox"
                        checked={selected.includes(s.id)}
                        disabled={s.status === "external_reference"}
                        onChange={() => toggle(s.id)}
                      />
                      <button
                        className="source-open"
                        onClick={() => openSource(s.id)}
                      >
                        <span>
                          {icon(s.kind)}
                          {s.title}
                        </span>
                        <small>
                          <span className="status-dot" />
                          {s.status.replaceAll("_", " ")}
                          {s.status === "ready" && <Check size={12} />}
                        </small>
                      </button>
                      <details className="source-options">
                        <summary aria-label={`Options for ${s.title}`}>
                          ⋯
                        </summary>
                        <div>
                          <button
                            disabled={
                              busy ||
                              s.kind === "upload" ||
                              s.status === "external_reference"
                            }
                            onClick={() =>
                              void operation(() =>
                                api(`${base}/${s.id}/refresh`, {
                                  method: "POST",
                                }),
                              )
                            }
                          >
                            Refresh source
                          </button>
                          <button onClick={() => setRemoving(s.id)}>
                            <Trash2 size={13} />
                            Remove source
                          </button>
                        </div>
                      </details>
                      {s.error_message && (
                        <p className="source-error">{s.error_message}</p>
                      )}
                      {s.kind === "module" && s.metadata.items && (
                        <ul className="module-items">
                          {s.metadata.items.map((item, i) => (
                            <li key={i}>
                              {sources.some(
                                (s) =>
                                  s.source_key === item.source_key &&
                                  s.status !== "external_reference",
                              ) && (
                                <input
                                  type="checkbox"
                                  aria-label={`Select module item ${item.title}`}
                                  checked={sources.some(
                                    (s) =>
                                      s.source_key === item.source_key &&
                                      selected.includes(s.id),
                                  )}
                                  onChange={() => {
                                    const target = sources.find(
                                      (s) => s.source_key === item.source_key,
                                    );
                                    if (target) toggle(target.id);
                                  }}
                                />
                              )}
                              <button
                                disabled={
                                  !sources.some(
                                    (s) => s.source_key === item.source_key,
                                  )
                                }
                                onClick={() => {
                                  const target = sources.find(
                                    (s) => s.source_key === item.source_key,
                                  );
                                  if (target) openSource(target.id);
                                }}
                              >
                                {item.title}
                                <small>{item.type}</small>
                              </button>
                            </li>
                          ))}
                        </ul>
                      )}
                      {removing === s.id && (
                        <div className="inline-confirm">
                          <p>
                            Remove downloaded text and its search index? Saved
                            answers keep their citation excerpts.
                          </p>
                          <button
                            className="button danger small"
                            disabled={busy}
                            onClick={() =>
                              void operation(async () => {
                                await api(`${base}/${s.id}`, {
                                  method: "DELETE",
                                });
                                setSelected(
                                  selected.filter((id) => id !== s.id),
                                );
                                setRemoving(null);
                              })
                            }
                          >
                            Remove
                          </button>
                          <button
                            className="text-button"
                            onClick={() => setRemoving(null)}
                          >
                            Keep source
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
              </details>
            ))}
          </div>
        </>
      )}
      <p className="source-footnote">
        Only ready, selected sources are available to chat and Studio. Files are
        indexed for search; video and external tools stay as references.
      </p>
    </div>
  );
}
