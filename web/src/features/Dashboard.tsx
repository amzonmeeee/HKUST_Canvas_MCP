import { useEffect, useState } from "react";
import {
  ArrowRight,
  Plus,
  RefreshCw,
  Search,
  FolderOpen,
  X,
  List,
  LayoutGrid,
  Settings2,
} from "lucide-react";
import { api } from "../api";
import { CanvasLink, EmptyState, ErrorNotice, Loading } from "../components";
import { CanvasConfiguration } from "./CanvasConfiguration";
import type { CanvasStatus, Course, Workspace } from "../types";

export function Dashboard({ navigate }: { navigate: (path: string) => void }) {
  const [configuring, setConfiguring] = useState(false);
  const [view, setView] = useState<"list" | "cards">(() => {
    try {
      return localStorage.getItem("canvas-workbench.dashboard-view") === "cards"
        ? "cards"
        : "list";
    } catch {
      return "list";
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem("canvas-workbench.dashboard-view", view);
    } catch {
      /* Optional preference. */
    }
  }, [view]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [status, setStatus] = useState<CanvasStatus | null>(null);
  const [courseError, setCourseError] = useState("");
  const [localError, setLocalError] = useState("");
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState("");
  const [actionError, setActionError] = useState("");
  const [truncated, setTruncated] = useState(false);

  async function load() {
    setLoading(true);
    setCourseError("");
    setLocalError("");
    const results = await Promise.allSettled([
      api<{ courses: Course[]; truncated: boolean }>("/api/canvas/courses"),
      api<{ workspaces: Workspace[] }>("/api/workspaces"),
      api<CanvasStatus>("/api/canvas/status"),
    ]);
    const [remote, local, connection] = results;
    if (remote.status === "fulfilled") {
      setCourses(remote.value.courses);
      setTruncated(remote.value.truncated);
    } else {
      setCourses([]);
      setCourseError(
        remote.reason.message || "Canvas courses could not be loaded.",
      );
    }
    if (local.status === "fulfilled") setWorkspaces(local.value.workspaces);
    else
      setLocalError(local.reason.message || "Workspaces could not be loaded.");
    if (connection.status === "fulfilled") setStatus(connection.value);
    else setStatus(null);
    setLoading(false);
  }
  useEffect(() => {
    void load();
  }, []);

  async function openCourse(course: Course) {
    const existing = workspaces.find(
      (workspace) => workspace.canvas_course_id === course.id,
    );
    if (existing) {
      navigate(`/workspace/${existing.id}`);
      return;
    }
    setBusy(course.id);
    setActionError("");
    try {
      const workspace = await api<Workspace>("/api/workspaces", {
        method: "POST",
        body: { kind: "canvas_course", canvas_course_id: course.id },
      });
      navigate(`/workspace/${workspace.id}`);
    } catch (error) {
      setActionError((error as Error).message);
    } finally {
      setBusy("");
    }
  }
  async function create(event: React.FormEvent) {
    event.preventDefault();
    setBusy("custom");
    setActionError("");
    try {
      const workspace = await api<Workspace>("/api/workspaces", {
        method: "POST",
        body: { kind: "custom", title: title.trim(), description },
      });
      navigate(`/workspace/${workspace.id}`);
    } catch (error) {
      setActionError((error as Error).message);
    } finally {
      setBusy("");
    }
  }
  const needle = query.trim().toLocaleLowerCase();
  const visible = courses.filter((course) =>
    `${course.course_code || ""} ${course.name} ${course.term_name || ""}`
      .toLocaleLowerCase()
      .includes(needle),
  );
  return (
    <>
      <header className="page-header">
        <div>
          <h1>Your study starts here.</h1>
          <p>Open a course, or make a workspace of your own.</p>
        </div>
        <button
          className="button secondary"
          disabled={loading || !!busy}
          onClick={() => void load()}
        >
          <RefreshCw size={16} aria-hidden="true" />
          Refresh
        </button>
      </header>
      <div className="connection-strip">
        <span
          className={`status-dot${status?.auth_verified ? "" : " neutral"}`}
        />
        <span>
          {status?.auth_verified
            ? "Canvas connected"
            : loading
              ? "Checking Canvas connection…"
              : "Canvas connection needs attention"}
        </span>
        {status?.profile_name && (
          <span className="muted">Chrome · {status.profile_name}</span>
        )}
        <div className="connection-actions">
          <button
            className="text-button"
            aria-expanded={configuring}
            onClick={() => setConfiguring(!configuring)}
          >
            <Settings2 size={16} />
            Configure Canvas
          </button>
          <CanvasLink />
        </div>
      </div>
      {configuring && (
        <section className="canvas-configuration">
          <CanvasConfiguration
            onChanged={() => {
              setConfiguring(false);
              void load();
            }}
          />
        </section>
      )}
      <div
        className="view-switch"
        role="group"
        aria-label="Course and workspace view"
      >
        <button
          type="button"
          aria-pressed={view === "list"}
          onClick={() => setView("list")}
        >
          <List size={16} />
          List view
        </button>
        <button
          type="button"
          aria-pressed={view === "cards"}
          onClick={() => setView("cards")}
        >
          <LayoutGrid size={16} />
          Card view
        </button>
      </div>
      {status && !status.auth_verified && (
        <ErrorNotice message={status.message} retry={() => void load()} />
      )}
      {actionError && <ErrorNotice message={actionError} />}
      <section className="course-section" aria-labelledby="courses-heading">
        <div className="section-header">
          <div>
            <h2 id="courses-heading">
              Canvas courses <span className="count">{courses.length}</span>
            </h2>
            <p>Active enrollments from your Chrome session.</p>
          </div>
          <label className="search-field">
            <Search size={17} aria-hidden="true" />
            <input
              type="search"
              placeholder="Find a course"
              aria-label="Find a course"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
        </div>
        {loading && !courses.length ? (
          <Loading>Loading your courses…</Loading>
        ) : courseError ? (
          <ErrorNotice message={courseError} retry={() => void load()} />
        ) : !courses.length ? (
          <EmptyState title="No active courses found">
            Check your Chrome profile and Canvas enrollments, then refresh.
          </EmptyState>
        ) : !visible.length ? (
          <EmptyState title="No matching courses">
            Try a course code, title or term.
          </EmptyState>
        ) : (
          <div
            className={`course-board${view === "cards" ? " card-view" : ""}`}
          >
            <div className="board-heading" aria-hidden="true">
              <span>Course</span>
              <span>Term</span>
              <span>Workspace</span>
            </div>
            {visible.map((course) => {
              const local = workspaces.find(
                (workspace) => workspace.canvas_course_id === course.id,
              );
              return (
                <button
                  key={course.id}
                  className="course-row"
                  disabled={!!busy}
                  onClick={() => void openCourse(course)}
                  aria-label={`Open ${course.course_code || course.name}`}
                >
                  <span className="course-title">
                    <strong>{course.course_code || "Canvas course"}</strong>
                    <span>{course.name}</span>
                    {local?.last_sync_at && (
                      <small className="course-sync">
                        Synced {new Date(local.last_sync_at).toLocaleString()}
                      </small>
                    )}
                  </span>
                  <span className="course-term">
                    {course.term_name || "Term not provided"}
                  </span>
                  <span className="course-open">
                    {busy === course.id
                      ? "Opening…"
                      : local
                        ? "Continue"
                        : "Open"}
                    <ArrowRight size={18} aria-hidden="true" />
                  </span>
                </button>
              );
            })}
          </div>
        )}
        {truncated && (
          <p className="muted">
            Showing up to 300 courses. This list may be incomplete.
          </p>
        )}
      </section>
      <section
        className="workspace-section"
        aria-labelledby="workspaces-heading"
      >
        <div className="section-header">
          <div>
            <h2 id="workspaces-heading">
              My workspaces <span className="count">{workspaces.length}</span>
            </h2>
            <p>
              Continue with your sources, conversations and study materials.
            </p>
          </div>
          <button
            className="button"
            disabled={!!busy}
            onClick={() => {
              setCreating(!creating);
              setActionError("");
            }}
          >
            {creating ? (
              <X size={16} aria-hidden="true" />
            ) : (
              <Plus size={16} aria-hidden="true" />
            )}
            {creating ? "Close form" : "New workspace"}
          </button>
        </div>
        {creating && (
          <form
            className="inline-form"
            onSubmit={(event) => void create(event)}
          >
            <label>
              Workspace name
              <input
                autoFocus
                required
                maxLength={160}
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="e.g. Research reading"
              />
            </label>
            <label>
              Description <span className="muted">(optional)</span>
              <textarea
                maxLength={2000}
                rows={2}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="What will you work on?"
              />
            </label>
            <button
              className="button"
              disabled={!!busy || !title.trim()}
              type="submit"
            >
              {busy === "custom" ? "Creating…" : "Create workspace"}
              <ArrowRight size={16} aria-hidden="true" />
            </button>
          </form>
        )}
        {localError ? (
          <ErrorNotice message={localError} retry={() => void load()} />
        ) : loading && !workspaces.length ? (
          <Loading>Loading workspaces…</Loading>
        ) : !workspaces.length ? (
          <EmptyState title="A place for each course—and everything else.">
            Opening a Canvas course saves a workspace here. Create a custom
            workspace for your own projects.
          </EmptyState>
        ) : (
          <div
            className={`workspace-list${view === "cards" ? " card-view" : ""}`}
          >
            {workspaces.map((workspace) => (
              <button
                className="workspace-row"
                key={workspace.id}
                onClick={() => navigate(`/workspace/${workspace.id}`)}
              >
                <FolderOpen size={21} aria-hidden="true" />
                <span>
                  <strong>{workspace.title}</strong>
                  <span>
                    {workspace.kind === "custom"
                      ? "Custom workspace"
                      : workspace.course_code || "Canvas course"}
                    {workspace.description ? ` · ${workspace.description}` : ""}
                  </span>
                </span>
                <ArrowRight size={17} aria-hidden="true" />
              </button>
            ))}
          </div>
        )}
      </section>
      <footer className="page-footer">
        Choose ready sources to start a conversation or create study materials.
      </footer>
    </>
  );
}
