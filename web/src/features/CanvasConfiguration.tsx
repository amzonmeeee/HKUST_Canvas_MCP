import { useEffect, useState } from "react";
import { api } from "../api";
import { ErrorNotice, Loading } from "../components";

type Profile = { id: string; name: string; selected: boolean };
export function CanvasConfiguration({ onChanged }: { onChanged: () => void }) {
  const [profiles, setProfiles] = useState<Profile[] | null>(null);
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [unlinked, setUnlinked] = useState(false);
  const [confirmUnlink, setConfirmUnlink] = useState(false);
  async function load() {
    setError("");
    try {
      const result = await api<{ profiles: Profile[]; unlinked: boolean }>(
        "/api/canvas/profiles",
      );
      setProfiles(result.profiles);
      setUnlinked(Boolean(result.unlinked));
      setSelected(result.profiles.find((p) => p.selected)?.id || "");
    } catch (problem) {
      setError((problem as Error).message);
    }
  }
  useEffect(() => {
    void load();
  }, []);
  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      await api("/api/canvas/profile", {
        method: "PUT",
        body: { profile_id: selected },
      });
      setSaved(true);
      setUnlinked(false);
      setConfirmUnlink(false);
      onChanged();
    } catch (problem) {
      setError((problem as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function unlink() {
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      await api("/api/canvas/profile", { method: "DELETE" });
      setUnlinked(true);
      setSelected("");
      setConfirmUnlink(false);
      onChanged();
    } catch (problem) {
      setError((problem as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="canvas-config-form">
      {error && <ErrorNotice message={error} retry={() => void load()} />}
      {unlinked && (
        <p role="status">
          Canvas: Not connected. Choose a profile to reconnect. Saved workspaces
          and cached sources are kept.
        </p>
      )}
      {profiles === null ? (
        !error && <Loading>Finding Chrome profiles…</Loading>
      ) : profiles.length === 0 ? (
        <p>
          No Chrome profiles found. Open Chrome and sign into HKUST Canvas, then
          retry.
        </p>
      ) : (
        <form onSubmit={(event) => void save(event)}>
          <label>
            Chrome profile
            <select
              aria-label="Chrome profile"
              value={selected}
              disabled={busy}
              required
              onChange={(event) => {
                setSelected(event.target.value);
                setSaved(false);
              }}
            >
              <option value="">Choose a Chrome profile</option>
              {profiles.map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.name}
                </option>
              ))}
            </select>
          </label>
          <button
            className="button secondary small"
            disabled={busy || !selected}
          >
            {busy
              ? "Saving…"
              : unlinked
                ? "Connect Canvas"
                : "Save Canvas profile"}
          </button>
          <p className="muted">
            Sign into canvas.ust.hk in this profile. Changing profiles clears
            pending write previews.
          </p>
        </form>
      )}
      {profiles !== null &&
        !unlinked &&
        (confirmUnlink ? (
          <div className="inline-confirm">
            <p>Unlink this Canvas profile?</p>
            <p>
              This removes the profile selection from HKUST Canvas Workbench,
              the CLI and MCP server. It will not delete your Chrome profile or
              sign you out of Canvas. Saved workspaces and cached sources are
              kept. Pending write previews are cancelled.
            </p>
            <button
              type="button"
              className="button secondary small"
              disabled={busy}
              onClick={() => setConfirmUnlink(false)}
            >
              Cancel
            </button>
            <button
              type="button"
              className="button secondary small"
              disabled={busy}
              onClick={() => void unlink()}
            >
              {busy ? "Unlinking…" : "Unlink"}
            </button>
          </div>
        ) : (
          <button
            type="button"
            className="text-button"
            disabled={busy}
            onClick={() => setConfirmUnlink(true)}
          >
            Unlink Canvas profile
          </button>
        ))}
      {saved && <p role="status">Canvas profile saved.</p>}
    </div>
  );
}
