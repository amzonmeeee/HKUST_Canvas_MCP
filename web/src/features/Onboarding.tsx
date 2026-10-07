import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { CanvasLink, ErrorNotice } from "../components";
import { CanvasConfiguration } from "./CanvasConfiguration";
import { ProviderSettings } from "./Providers";
import { LocalClients } from "./LocalClients";

const steps = [
  "Welcome",
  "Canvas",
  "AI provider",
  "Privacy & safety",
  "MCP clients",
  "Ready",
];

export function Onboarding({ onComplete }: { onComplete: () => void }) {
  const [step, setStep] = useState(0);
  const [acknowledged, setAcknowledged] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const title = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    title.current?.focus();
  }, [step]);
  async function finish() {
    setBusy(true);
    setError("");
    try {
      await api("/api/onboarding", {
        method: "PUT",
        body: { privacy_acknowledged: acknowledged },
      });
      onComplete();
    } catch (problem) {
      setError((problem as Error).message);
      setBusy(false);
    }
  }
  return (
    <section className="onboarding" aria-label="Set up Canvas Workbench">
      <ol className="setup-progress" aria-label="Setup progress">
        {steps.map((name, index) => (
          <li key={name} aria-current={index === step ? "step" : undefined}>
            {name}
          </li>
        ))}
      </ol>
      <h1 ref={title} tabIndex={-1}>
        {steps[step]}
      </h1>
      {error && <ErrorNotice message={error} />}
      {step === 0 && (
        <>
          <h2>Your Canvas. Your AI.</h2>
          <p>
            Bring your course sources, choose the model you already use, and
            study with answers that cite your materials.
          </p>
          <p>
            Connect Canvas and an AI provider now, or skip either and add them
            later in Settings. Your existing connections and saved work are
            kept.
          </p>
        </>
      )}
      {step === 1 && (
        <>
          <p>
            Use a Chrome profile signed into HKUST Canvas. Choose it and check
            the resolved account before continuing.
          </p>
          <CanvasConfiguration onChanged={() => {}} />
          <CanvasLink />
          <p>
            You can also continue with uploaded materials and connect Canvas
            later.
          </p>
        </>
      )}
      {step === 2 && (
        <>
          <p>
            Use an installed Codex or Claude Code CLI login, an official API, or
            a local model server. Connection tests send a short test prompt and
            may use your account quota or API billing.
          </p>
          <ProviderSettings />
        </>
      )}
      {step === 3 && (
        <>
          <p>
            Canvas cookies stay in the backend on this computer. API keys stay
            in your system credential store.
          </p>
          <p>
            When you send or generate, a cloud provider receives your prompt,
            relevant conversation history and selected/retrieved course
            excerpts. Local endpoints receive the same context on their
            configured machine.
          </p>
          <p>
            MCP starts read-only. Canvas writes require a preview and explicit
            approval; always verify important submissions, grades and deadlines
            in Canvas. Unlinking preserves Chrome login and saved sources.
          </p>
          <p>
            This independent project is not affiliated with HKUST, Instructure
            or the AI providers.
          </p>
          <label className="check-line">
            <input
              type="checkbox"
              checked={acknowledged}
              onChange={(event) => setAcknowledged(event.target.checked)}
            />
            I understand how my data is used and how Canvas writes are
            confirmed.
          </label>
        </>
      )}
      {step === 4 && (
        <>
          <p>
            Optional: connect Canvas tools to your Codex or Claude desktop
            client. This is separate from selecting the provider used inside
            this workbench.
          </p>
          <LocalClients desktop />
        </>
      )}
      {step === 5 && (
        <>
          <h2>Open your course, or start with your own materials.</h2>
          <p>
            Choose a course on the dashboard, find sources, sync selected
            material and ask your first question. If you skipped Canvas, create
            a workspace and upload a file or add text.
          </p>
          <p>You can revisit setup and change connections from Settings.</p>
        </>
      )}
      <div className="setup-actions">
        {step > 0 && (
          <button
            className="button secondary"
            disabled={busy}
            onClick={() => setStep(step - 1)}
          >
            Back
          </button>
        )}
        {step < 5 ? (
          <button
            className="button"
            disabled={step === 3 && !acknowledged}
            onClick={() => setStep(step + 1)}
          >
            {[1, 2, 4].includes(step) ? "Continue / skip for now" : "Continue"}
          </button>
        ) : (
          <button
            className="button"
            disabled={busy || !acknowledged}
            onClick={() => void finish()}
          >
            {busy ? "Saving…" : "Open workbench"}
          </button>
        )}
      </div>
    </section>
  );
}
