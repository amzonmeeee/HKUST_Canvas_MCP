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
  async function load() {
    setError("");
    try {
      const result = await api<{ profiles: Profile[] }>("/api/canvas/profiles");
      setProfiles(result.profiles);
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
            {busy ? "Saving…" : "Save Canvas profile"}
          </button>
          <p className="muted">
            Sign into canvas.ust.hk in this profile. Changing profiles clears
            pending write previews.
          </p>
        </form>
      )}
      {saved && <p role="status">Canvas profile saved.</p>}
    </div>
  );
}
