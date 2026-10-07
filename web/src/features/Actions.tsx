import { useEffect, useState } from "react";
import { api } from "../api";
import { ErrorNotice } from "../components";
import type { Preview, Workspace } from "../types";

const labels: Record<string, string> = {
  get_my_submission_status: "My submission status",
  get_my_peer_reviews_todo: "Peer reviews to do",
  list_conversations: "List Inbox conversations",
  get_conversation_details: "Read Inbox conversation",
  get_course_structure: "Course structure",
  list_module_items: "Module items",
  get_assignment_details: "Assignment details",
  list_course_assignments: "Course assignments",
  get_course_overview: "Course overview",
  get_course_syllabus: "Course syllabus",
  post_discussion_entry: "Post to a discussion",
  reply_to_discussion_entry: "Reply to a discussion entry",
  add_submission_comment: "Comment on my submission",
  send_conversation: "Send Inbox message",
  reply_to_conversation: "Reply to Inbox conversation",
  mark_module_item_done: "Mark module item done / undo",
};
const writeActions = new Set([
  "post_discussion_entry",
  "reply_to_discussion_entry",
  "add_submission_comment",
  "send_conversation",
  "reply_to_conversation",
  "mark_module_item_done",
]);
export function actionLabel(name: string) {
  return labels[name] || name.replaceAll("_", " ");
}

export function Facts({ value }: { value: unknown }) {
  if (value === null || value === undefined)
    return <span className="muted">—</span>;
  if (Array.isArray(value))
    return (
      <ul className="fact-list">
        {value.map((v, i) => (
          <li key={i}>
            <Facts value={v} />
          </li>
        ))}
      </ul>
    );
  if (typeof value === "object")
    return (
      <dl className="action-facts">
        {Object.entries(value).map(([k, v]) => (
          <div key={k}>
            <dt>{k.replaceAll("_", " ")}</dt>
            <dd>
              <Facts value={v} />
            </dd>
          </div>
        ))}
      </dl>
    );
  return <span className="fact-value">{String(value)}</span>;
}

export function WritePreview({
  workspaceId,
  preview,
  onFinished,
}: {
  workspaceId: string;
  preview: Preview;
  onFinished: () => void;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [result, setResult] = useState<unknown>(null),
    [finished, setFinished] = useState(false);
  async function confirm() {
    setBusy(true);
    setError("");
    try {
      setResult(
        await api(
          `/api/workspaces/${workspaceId}/actions/${preview.id}/confirm`,
          { method: "POST", body: { approved: true } },
        ),
      );
      setFinished(true);
      onFinished();
    } catch (p) {
      setError((p as Error).message);
      setFinished(true);
      onFinished();
    } finally {
      setBusy(false);
    }
  }
  async function cancel() {
    setBusy(true);
    try {
      await api(`/api/workspaces/${workspaceId}/actions/${preview.id}`, {
        method: "DELETE",
      });
      setFinished(true);
      setResult({ status: "cancelled", written: false });
      onFinished();
    } catch (p) {
      setError((p as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <article className="write-preview">
      <h3>{actionLabel(preview.tool)}</h3>
      <p>
        <strong>Human approval required</strong>
      </p>
      <p className="muted">
        Review the exact account, target, recipients and content before
        confirming. This will change Canvas.
      </p>
      <h4>Account</h4>
      <Facts value={preview.account} />
      <h4>Target</h4>
      <Facts value={preview.target} />
      <h4>Content</h4>
      <Facts value={preview.payload} />
      {error && <ErrorNotice message={error} />}
      {result !== null && (
        <div role="status">
          <Facts value={result} />
        </div>
      )}
      {!finished && (
        <div className="form-actions">
          <button
            className="button primary"
            disabled={busy}
            onClick={() => void confirm()}
          >
            {busy ? "Processing…" : "Confirm Canvas write"}
          </button>
          <button
            className="button secondary"
            disabled={busy}
            onClick={() => void cancel()}
          >
            Cancel action
          </button>
        </div>
      )}
      {finished && error && (
        <p className="muted">
          This preview has been consumed. Check Canvas before preparing another
          action; a disconnected request may have succeeded.
        </p>
      )}
    </article>
  );
}

type Property = {
  type?: string | string[];
  enum?: string[];
  description?: string;
  default?: unknown;
};
type Tool = {
  name: string;
  description: string;
  parameters: { properties: Record<string, Property>; required?: string[] };
};
export function LiveActions({
  workspace,
  onPreview,
}: {
  workspace: Workspace;
  onPreview: (p: Preview) => void;
}) {
  const [tools, setTools] = useState<Tool[]>([]),
    [name, setName] = useState(""),
    [values, setValues] = useState<Record<string, string | boolean>>({}),
    [result, setResult] = useState<unknown>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    void api<{ tools: Tool[] }>(`/api/workspaces/${workspace.id}/actions`)
      .then((r) => setTools(r.tools))
      .catch((p) => setError((p as Error).message));
  }, [workspace.id]);
  const tool = tools.find((t) => t.name === name),
    write = writeActions.has(name);
  function type(p: Property) {
    return Array.isArray(p.type) ? p.type.find((t) => t !== "null") : p.type;
  }
  async function execute(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const args: Record<string, unknown> = {};
      for (const [key, p] of Object.entries(tool!.parameters.properties)) {
        const value =
          key === "course_id" && workspace.canvas_course_id
            ? workspace.canvas_course_id
            : values[key];
        if (value === undefined || value === "") continue;
        args[key] =
          type(p) === "array"
            ? String(value)
                .split(",")
                .map((v) => v.trim())
                .filter(Boolean)
            : type(p) === "integer"
              ? Number(value)
              : value;
      }
      const r = await api<{
        requires_human_approval?: boolean;
        preview?: Preview;
      }>(`/api/workspaces/${workspace.id}/actions/preview`, {
        method: "POST",
        body: { name, arguments: args },
      });
      if (r.preview) onPreview(r.preview);
      else setResult(r);
    } catch (p) {
      setError((p as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <details className="live-actions">
      <summary>
        Live Canvas actions <small>Reads and write previews</small>
      </summary>
      <p>
        Fetch current Canvas state, or prepare an action for your approval.
        These controls work without an AI provider.
      </p>
      {error && <ErrorNotice message={error} />}
      <form className="compact-form" onSubmit={(e) => void execute(e)}>
        <div className="action-picker">
          {[
            { write: false, label: "Check Canvas" },
            { write: true, label: "Prepare a write" },
          ].map((group) => (
            <fieldset key={group.label}>
              <legend>{group.label}</legend>
              <div className="action-buttons">
                {tools
                  .filter((item) => writeActions.has(item.name) === group.write)
                  .map((item) => (
                    <button
                      key={item.name}
                      type="button"
                      aria-pressed={name === item.name}
                      disabled={busy}
                      onClick={() => {
                        setName(item.name);
                        setValues(
                          item.name === "mark_module_item_done"
                            ? { done: true }
                            : {},
                        );
                        setResult(null);
                        setError("");
                      }}
                    >
                      {actionLabel(item.name)}
                    </button>
                  ))}
              </div>
            </fieldset>
          ))}
        </div>
        {tool &&
          Object.entries(tool.parameters.properties)
            .filter(
              ([key]) => !(key === "course_id" && workspace.canvas_course_id),
            )
            .map(([key, p]) => {
              const required = tool.parameters.required?.includes(key),
                label = key.replaceAll("_", " ") + (required ? " *" : ""),
                value = values[key];
              if (type(p) === "boolean")
                return (
                  <label key={key} className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={Boolean(value)}
                      onChange={(e) =>
                        setValues({ ...values, [key]: e.target.checked })
                      }
                    />
                    {label}
                    {key === "done" && (
                      <small>Checked = mark done; unchecked = undo</small>
                    )}
                  </label>
                );
              if (p.enum)
                return (
                  <label key={key}>
                    {label}
                    <select
                      value={String(value || "")}
                      required={required}
                      onChange={(e) =>
                        setValues({ ...values, [key]: e.target.value })
                      }
                    >
                      <option value="">Choose…</option>
                      {p.enum.map((v) => (
                        <option key={v} value={v}>
                          {v}
                        </option>
                      ))}
                    </select>
                  </label>
                );
              if (["message", "body", "comment"].includes(key))
                return (
                  <label key={key}>
                    {label}
                    <textarea
                      required={required}
                      rows={4}
                      value={String(value || "")}
                      onChange={(e) =>
                        setValues({ ...values, [key]: e.target.value })
                      }
                    />
                  </label>
                );
              return (
                <label key={key}>
                  {label}
                  <input
                    required={required}
                    type={type(p) === "integer" ? "number" : "text"}
                    value={String(value ?? "")}
                    placeholder={
                      type(p) === "array"
                        ? "Comma-separated Canvas IDs"
                        : key.endsWith("_id")
                          ? "Canvas ID from the page URL"
                          : ""
                    }
                    onChange={(e) =>
                      setValues({ ...values, [key]: e.target.value })
                    }
                  />
                </label>
              );
            })}
        {tool && (
          <button className="button secondary small" disabled={busy}>
            {busy
              ? "Checking Canvas…"
              : write
                ? "Prepare exact preview"
                : "Fetch from Canvas"}
          </button>
        )}
      </form>
      {result !== null && (
        <div className="live-result" role="status">
          <h3>Canvas result</h3>
          <Facts value={result} />
        </div>
      )}
    </details>
  );
}
