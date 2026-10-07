import { useEffect, useState } from "react";
import {
  Archive,
  ArchiveRestore,
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
import type { Citation, Workspace } from "../types";
import { SourcesPanel } from "./Sources";
import { ChatPanel } from "./Chat";
import { StudioPanel } from "./Studio";
import { SourceViewer } from "./StudyContent";
import { PanelResizeHandle } from "./PanelResizeHandle";
import { usePanelLayout } from "./usePanelLayout";

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
  const layout = usePanelLayout(sourcesOpen, studioOpen);
  const [selected, setSelected] = useState<string[]>([]);
  const [providerId, setProviderId] = useState("");
  const [viewer, setViewer] = useState<{
    sourceId?: string;
    citation?: Citation;
  } | null>(null);
  const [notesVersion, setNotesVersion] = useState(0);
  async function load() {
    setError("");
    try {
      setWorkspace(await api<Workspace>(`/api/workspaces/${workspaceId}`));
    } catch (problem) {
      setError((problem as Error).message);
    }
  }
  useEffect(() => {
    setSelected([]);
    setProviderId("");
    setViewer(null);
    setWorkspace(null);
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
  async function archive() {
    if (!workspace) return;
    setBusy(true);
    setError("");
    try {
      const updated = await api<Workspace>(`/api/workspaces/${workspaceId}`, {
        method: "PATCH",
        body: { archived: !workspace.archived },
      });
      setWorkspace(updated);
      if (updated.archived) navigate("/");
    } catch (problem) {
      setError((problem as Error).message);
    } finally {
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
              onClick={() => void archive()}
            >
              {workspace.archived ? (
                <ArchiveRestore size={15} />
              ) : (
                <Archive size={15} />
              )}
              {workspace.archived ? "Restore workspace" : "Archive workspace"}
            </button>
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
              Delete workspace…
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
              aria-label="Confirm workspace deletion"
            >
              <p>
                Delete “{workspace.title}” and its saved content? Your Canvas
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
            ref={layout.container}
            style={layout.style}
            className={`workbench${sourcesOpen ? "" : " sources-closed"}${studioOpen ? "" : " studio-closed"}`}
          >
            <section
              id={`sources-${workspaceId}`}
              className="workbench-panel sources-panel"
            >
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
                <SourcesPanel
                  key={workspaceId}
                  workspace={workspace}
                  selected={selected}
                  setSelected={setSelected}
                  openSource={(sourceId) => setViewer({ sourceId })}
                />
              )}
            </section>
            <PanelResizeHandle
              side="sources"
              size={layout.sizes.sources}
              minimum={layout.minimum.sources}
              maximum={layout.maximum.sources}
              disabled={!sourcesOpen}
              controls={`sources-${workspaceId}`}
              onResize={(size) => layout.resize("sources", size)}
              onReset={layout.reset}
            />
            <section className="workbench-panel chat-panel">
              <h2 className="panel-title">
                <span>
                  <MessageSquare size={18} aria-hidden="true" />
                  Conversation
                </span>
              </h2>
              <ChatPanel
                key={workspaceId}
                workspace={workspace}
                sourceIds={selected}
                providerId={providerId}
                setProviderId={setProviderId}
                openCitation={(citation) => setViewer({ citation })}
                notesChanged={() => setNotesVersion((v) => v + 1)}
                navigate={navigate}
              />
            </section>
            <PanelResizeHandle
              side="studio"
              size={layout.sizes.studio}
              minimum={layout.minimum.studio}
              maximum={layout.maximum.studio}
              disabled={!studioOpen}
              controls={`studio-${workspaceId}`}
              onResize={(size) => layout.resize("studio", size)}
              onReset={layout.reset}
            />
            <section
              id={`studio-${workspaceId}`}
              className="workbench-panel studio-panel"
            >
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
                <StudioPanel
                  key={workspaceId}
                  workspaceId={workspaceId}
                  sourceIds={selected}
                  providerId={providerId}
                  notesVersion={notesVersion}
                  openCitation={(citation) => setViewer({ citation })}
                />
              )}
            </section>
          </div>
          {viewer && (
            <SourceViewer
              workspaceId={workspaceId}
              {...viewer}
              close={() => setViewer(null)}
            />
          )}
        </>
      )}
    </>
  );
}
