import { useEffect, useState } from "react";
import {
  ArrowLeft,
  FileText,
  MessageSquare,
  Layers,
  Pencil,
  Trash2,
  Check,
  X,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { api } from "../api";
import { CanvasLink, ErrorNotice, Loading } from "../components";
import type { Workspace } from "../types";

export function WorkspacePage({
  workspaceId,
  navigate,
}: {
  workspaceId: string;
  navigate: (path: string) => void;
}) {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(true);
  const [studioOpen, setStudioOpen] = useState(true);
  async function load() {
    setError("");
    try {
      setWorkspace(await api<Workspace>(`/api/workspaces/${workspaceId}`));
    } catch (problem) {
      setError((problem as Error).message);
    }
  }
  useEffect(() => {
    void load();
  }, [workspaceId]);
  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      setWorkspace(
        await api<Workspace>(`/api/workspaces/${workspaceId}`, {
          method: "PATCH",
          body: { title: title.trim(), description },
        }),
      );
      setEditing(false);
    } catch (problem) {
      setError((problem as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    setBusy(true);
    setError("");
    try {
      await api(`/api/workspaces/${workspaceId}`, { method: "DELETE" });
      navigate("/");
    } catch (problem) {
      setError((problem as Error).message);
      setBusy(false);
    }
  }
  return (
    <>
      <button className="back-link" onClick={() => navigate("/")}>
        <ArrowLeft size={16} aria-hidden="true" />
        All workspaces
      </button>
      {error && <ErrorNotice message={error} retry={() => void load()} />}
      {!workspace ? (
        !error && <Loading>Opening workspace…</Loading>
      ) : (
        <>
          <header className="page-header workspace-header">
            <div>
              <h1>{workspace.title}</h1>
              <p>
                {[workspace.course_code, workspace.term_name]
                  .filter(Boolean)
                  .join(" · ") || "Custom workspace"}
                <span className="local-inline">Saved on this computer</span>
              </p>
            </div>
            {workspace.canvas_course_id && (
              <CanvasLink courseId={workspace.canvas_course_id} />
            )}
          </header>
          {workspace.description && !editing && (
            <p className="workspace-description">{workspace.description}</p>
          )}
          <div className="workspace-actions">
            <button
              className="text-button"
              disabled={busy}
              onClick={() => {
                setEditing(!editing);
                setTitle(workspace.title);
                setDescription(workspace.description);
                setDeleting(false);
              }}
            >
              <Pencil size={15} aria-hidden="true" />
              Edit workspace
            </button>
            <button
              className="text-button"
              disabled={busy}
              onClick={() => {
                setDeleting(!deleting);
                setEditing(false);
              }}
            >
              <Trash2 size={15} aria-hidden="true" />
              Delete local workspace
            </button>
          </div>
          {editing && (
            <form
              className="inline-form"
              onSubmit={(event) => void save(event)}
            >
              <label>
                Workspace name
                <input
                  autoFocus
                  required
                  maxLength={160}
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                />
              </label>
              <label>
                Description
                <textarea
                  rows={2}
                  maxLength={2000}
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                />
              </label>
              <div className="form-actions">
                <button
                  type="submit"
                  className="button"
                  disabled={busy || !title.trim()}
                >
                  <Check size={16} aria-hidden="true" />
                  {busy ? "Saving…" : "Save changes"}
                </button>
                <button
                  className="button secondary"
                  type="button"
                  onClick={() => setEditing(false)}
                  disabled={busy}
                >
                  <X size={16} aria-hidden="true" />
                  Cancel
                </button>
              </div>
            </form>
          )}
          {deleting && (
            <div
              className="delete-confirm"
              role="region"
              aria-label="Confirm local workspace deletion"
            >
              <p>
                Delete “{workspace.title}” from this computer? Your Canvas
                course and its content will remain available.
              </p>
              <div className="form-actions">
                <button
                  className="button danger"
                  disabled={busy}
                  onClick={() => void remove()}
                >
                  {busy ? "Deleting…" : "Delete workspace"}
                </button>
                <button
                  className="button secondary"
                  disabled={busy}
                  onClick={() => setDeleting(false)}
                >
                  Keep workspace
                </button>
              </div>
            </div>
          )}
          <div
            className={`workbench${sourcesOpen ? "" : " sources-closed"}${studioOpen ? "" : " studio-closed"}`}
          >
            <section className="workbench-panel sources-panel">
              <button
                className="panel-title"
                aria-expanded={sourcesOpen}
                onClick={() => setSourcesOpen(!sourcesOpen)}
              >
                <span>
                  <FileText size={18} aria-hidden="true" />
                  Sources
                </span>
                {sourcesOpen ? (
                  <ChevronUp size={16} />
                ) : (
                  <ChevronDown size={16} />
                )}
              </button>
              {sourcesOpen && (
                <div className="panel-body">
                  <p className="phase-label">Next: source sync</p>
                  <h3>Your course materials belong here.</h3>
                  <p>
                    Pages, files and module items will become selectable local
                    sources in Phase B.
                  </p>
                  {workspace.canvas_course_id ? (
                    <CanvasLink courseId={workspace.canvas_course_id} />
                  ) : (
                    <p className="muted">
                      File uploads and manual sources will arrive with source
                      sync.
                    </p>
                  )}
                </div>
              )}
            </section>
            <section className="workbench-panel chat-panel">
              <h2 className="panel-title">
                <span>
                  <MessageSquare size={18} aria-hidden="true" />
                  Conversation
                </span>
              </h2>
              <div className="chat-empty">
                <span className="workspace-emblem" aria-hidden="true">
                  <MessageSquare size={30} />
                </span>
                <h2>A workspace you can return to.</h2>
                <p>
                  Your workspace is saved. Grounded chat will arrive after local
                  source sync and model providers are ready.
                </p>
                <p className="muted">
                  You can already use the existing Canvas MCP server with your
                  preferred MCP client.
                </p>
                <button
                  className="button secondary"
                  onClick={() => navigate("/settings")}
                >
                  View MCP settings
                  <ArrowLeft
                    className="arrow-forward"
                    size={16}
                    aria-hidden="true"
                  />
                </button>
              </div>
            </section>
            <section className="workbench-panel studio-panel">
              <button
                className="panel-title"
                aria-expanded={studioOpen}
                onClick={() => setStudioOpen(!studioOpen)}
              >
                <span>
                  <Layers size={18} aria-hidden="true" />
                  Study Studio
                </span>
                {studioOpen ? (
                  <ChevronUp size={16} />
                ) : (
                  <ChevronDown size={16} />
                )}
              </button>
              {studioOpen && (
                <div className="panel-body">
                  <p className="phase-label">After grounded chat</p>
                  <h3>Turn understanding into practice.</h3>
                  <ul className="studio-list">
                    <li>
                      Quizzes<span>Practice</span>
                    </li>
                    <li>
                      Flashcards<span>Recall</span>
                    </li>
                    <li>
                      Study guides<span>Review</span>
                    </li>
                  </ul>
                  <p className="muted">
                    Study outputs and local notes are planned for later phases.
                  </p>
                </div>
              )}
            </section>
          </div>
        </>
      )}
    </>
  );
}
