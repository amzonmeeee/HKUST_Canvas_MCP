import { useEffect, useRef, useState } from "react";
import { AudioLines, Download, Square, Trash2 } from "lucide-react";
import { api } from "../api";
import { ErrorNotice } from "../components";
import type { Source, TranscriberStatus } from "../types";

const MODELS = [
  ["auto", "Automatic (Qwen3-ASR 1.7B on the GPU)"],
  ["qwen3-asr-0.6b", "Qwen3-ASR 0.6B (less memory)"],
  ["whisper-large-v3", "Whisper large-v3 (CPU, slow)"],
] as const;

function gigabytes(bytes: number) {
  return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
}

function progressText(job: NonNullable<TranscriberStatus["job"]>) {
  const step = job.event.replaceAll("_", " ");
  if (job.segment && job.segments)
    return `${step} ${job.segment}/${job.segments}${job.audio_time ? ` · ${job.audio_time}` : ""}`;
  return step;
}

/** Local transcription controls for an HKUST RVC recording source. */
export function RecordingTranscription({
  workspaceId,
  source,
  onTranscribed,
}: {
  workspaceId: string;
  source: Source;
  onTranscribed: () => void;
}) {
  const [status, setStatus] = useState<TranscriberStatus | null>(null),
    [model, setModel] = useState("auto"),
    [confirmRemove, setConfirmRemove] = useState(false),
    [error, setError] = useState("");
  const reported = useRef(false);
  const job = status?.job;
  const running = job?.state === "running";
  const mine =
    job?.kind === "transcribe" && job.source_id === source.id ? job : null;

  async function load() {
    const next = await api<TranscriberStatus>("/api/transcriber");
    setStatus(next);
    const done = next.job;
    if (
      done?.kind === "transcribe" &&
      done.source_id === source.id &&
      done.state === "complete" &&
      !reported.current
    ) {
      reported.current = true;
      onTranscribed();
    }
  }
  useEffect(() => {
    void load().catch((p) => setError((p as Error).message));
  }, [source.id]);
  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(
      () => void load().catch(() => {}),
      2000,
    );
    return () => window.clearInterval(timer);
  }, [running]);

  async function act(action: () => Promise<unknown>) {
    setError("");
    try {
      await action();
      reported.current = false;
      await load();
    } catch (p) {
      setError((p as Error).message);
    }
  }

  if (!status) return null;
  return (
    <section className="recording-panel" aria-label="Local transcription">
      <h3>
        <AudioLines size={16} aria-hidden="true" /> Transcript
      </h3>
      {error && <ErrorNotice message={error} />}
      {!status.installed && !(running && job?.kind === "install") && (
        <>
          <p>
            Make a timestamped transcript on this Mac. The transcript becomes a
            source that chat and Studio can cite. Audio is not sent to a
            server.
          </p>
          <p className="muted">
            First install the transcriber. It downloads approximately 4–5 GB
            (Python, FFmpeg and a speech model) into the app data folder. You
            can remove it later.
          </p>
          <label className="recording-model">
            Speech model
            <select value={model} onChange={(e) => setModel(e.target.value)}>
              {MODELS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <button
            className="button"
            disabled={running}
            onClick={() =>
              void act(() =>
                api("/api/transcriber/install", {
                  method: "POST",
                  body: { model },
                }),
              )
            }
          >
            <Download size={15} /> Install transcriber
          </button>
        </>
      )}
      {running && job && (job.kind === "install" || mine) && (
        <div className="recording-progress" role="status">
          <span className="status-dot" />
          {job.kind === "install" ? "Installing: " : "Transcribing: "}
          {progressText(job)}
          <button
            className="text-button"
            onClick={() =>
              void act(() => api("/api/transcriber/stop", { method: "POST" }))
            }
          >
            <Square size={13} /> Stop
          </button>
        </div>
      )}
      {running && job?.kind === "transcribe" && !mine && (
        <p className="muted">
          The transcriber is busy with “{job.title}”. Try again when it
          completes.
        </p>
      )}
      {status.installed && !running && (
        <>
          {source.status === "ready" ? (
            <p>
              The transcript is ready and is part of this workspace's sources.
            </p>
          ) : (
            <p>
              Make a timestamped transcript on this Mac with{" "}
              {status.model || "the installed model"}. A 90-minute lecture
              takes approximately 15–20 minutes on the GPU.
            </p>
          )}
          <button
            className="button"
            onClick={() =>
              void act(() =>
                api(
                  `/api/workspaces/${workspaceId}/sources/${source.id}/transcribe`,
                  { method: "POST" },
                ),
              )
            }
          >
            <AudioLines size={15} />
            {source.status === "ready"
              ? "Transcribe again"
              : source.error_code === "transcription_cancelled" ||
                  source.error_code === "transcription_interrupted"
                ? "Continue transcription"
                : "Transcribe"}
          </button>
        </>
      )}
      {job && !running && job.message && (mine || job.kind === "install") && (
        <p className="source-error">{job.message}</p>
      )}
      {status.installed && !running && (
        <div className="recording-remove">
          {confirmRemove ? (
            <>
              <span>
                Remove the transcriber and its models (
                {gigabytes(status.disk_bytes)})? Transcripts stay.
              </span>
              <button
                className="button danger small"
                onClick={() =>
                  void act(async () => {
                    await api("/api/transcriber", { method: "DELETE" });
                    setConfirmRemove(false);
                  })
                }
              >
                Remove
              </button>
              <button
                className="text-button"
                onClick={() => setConfirmRemove(false)}
              >
                Keep
              </button>
            </>
          ) : (
            <button
              className="text-button"
              onClick={() => setConfirmRemove(true)}
            >
              <Trash2 size={13} /> Remove transcriber (
              {gigabytes(status.disk_bytes)})
            </button>
          )}
        </div>
      )}
    </section>
  );
}
