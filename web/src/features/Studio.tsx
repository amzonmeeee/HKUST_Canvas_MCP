import { VisualMaterial } from "./VisualMaterial";
import { useEffect, useState } from "react";
import {
  Plus,
  Bookmark,
  Download,
  Trash2,
  ArrowLeft,
  CircleHelp,
  Layers,
  BookOpen,
  FileText,
  Table2,
  Network,
  Presentation,
  ChartNoAxesCombined,
} from "lucide-react";
import { api } from "../api";
import { ErrorNotice, Loading } from "../components";
import { StudyMarkdown, CitationList } from "./StudyContent";
import type { Artifact, Citation, Note, Provider } from "../types";

const difficulties = ["introductory", "intermediate", "advanced"] as const;
const difficultyLabels = ["Introductory", "Intermediate", "Advanced"];

export function StudioPanel({
  workspaceId,
  sourceIds,
  providerId,
  notesVersion,
  openCitation,
}: {
  workspaceId: string;
  sourceIds: string[];
  providerId: string;
  notesVersion: number;
  openCitation: (c: Citation) => void;
}) {
  const base = `/api/workspaces/${workspaceId}`;
  const [provider, setProvider] = useState<Provider | null>(null);
  useEffect(() => {
    setProvider(null);
    if (providerId)
      void api<{ providers: Provider[] }>("/api/providers")
        .then((r) =>
          setProvider(r.providers?.find((p) => p.id === providerId) || null),
        )
        .catch(() => {});
  }, [providerId]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]),
    [notes, setNotes] = useState<Note[]>([]),
    [kind, setKind] = useState<Artifact["kind"]>("quiz"),
    [prompt, setPrompt] = useState(""),
    [template, setTemplate] = useState("automatic"),
    [topic, setTopic] = useState(""),
    [count, setCount] = useState(5),
    [difficulty, setDifficulty] =
      useState<(typeof difficulties)[number]>("intermediate"),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [active, setActive] = useState<Artifact | null>(null),
    [note, setNote] = useState<Note | null>(null),
    [title, setTitle] = useState(""),
    [content, setContent] = useState(""),
    [editing, setEditing] = useState(false),
    [tab, setTab] = useState("materials"),
    [answers, setAnswers] = useState<Record<number, number>>({}),
    [flipped, setFlipped] = useState<number[]>([]),
    [revealed, setRevealed] = useState<number[]>([]),
    [removing, setRemoving] = useState<string | null>(null),
    [saved, setSaved] = useState(false);
  const [language, setLanguage] = useState("automatic"),
    [orientation, setOrientation] = useState("landscape"),
    [visualStyle, setVisualStyle] = useState("automatic"),
    [slideFormat, setSlideFormat] = useState("detailed");
  const [excerptSaved, setExcerptSaved] = useState<number[]>([]);
  async function load() {
    const [a, n] = await Promise.all([
      api<{ artifacts: Artifact[] }>(`${base}/artifacts`),
      api<{ notes: Note[] }>(`${base}/notes`),
    ]);
    setArtifacts(a.artifacts);
    setNotes(n.notes);
  }
  useEffect(() => {
    void load()
      .catch((p) => setError((p as Error).message))
      .finally(() => setLoading(false));
  }, [workspaceId, notesVersion]);
  async function generate(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const a = await api<Artifact>(`${base}/artifacts/generate`, {
        method: "POST",
        body: {
          provider_id: providerId,
          source_ids: sourceIds,
          kind,
          topic,
          count,
          difficulty,
          prompt,
          template,
          language,
          orientation,
          visual_style: visualStyle,
          slide_format: slideFormat,
        },
      });
      openArtifact(a);
      await load();
    } catch (p) {
      setError((p as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function openArtifact(a: Artifact) {
    setActive(a);
    setNote(null);
    setEditing(false);
    setAnswers({});
    setFlipped([]);
    setRevealed([]);
    setSaved(false);
    setExcerptSaved([]);
    setRemoving(null);
  }
  async function saveArtifact(index?: number) {
    try {
      await api(`${base}/notes`, {
        method: "POST",
        body: {
          title:
            index === undefined
              ? active!.title
              : `${active!.title.slice(0, 140)} — item ${index + 1}`,
          content: "",
          artifact_id: active!.id,
          ...(index === undefined ? {} : { artifact_index: index }),
        },
      });
      if (index === undefined) setSaved(true);
      else setExcerptSaved([...excerptSaved, index]);
      await load();
    } catch (p) {
      setError((p as Error).message);
    }
  }
  function editNote(n?: Note) {
    setActive(null);
    setNote(n || null);
    setTitle(n?.title || "");
    setContent(n?.content || "");
    setEditing(true);
    setTab("notes");
    setRemoving(null);
  }
  async function saveNote(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const n = await api<Note>(
        note ? `${base}/notes/${note.id}` : `${base}/notes`,
        { method: note ? "PUT" : "POST", body: { title, content } },
      );
      setNote(n);
      setEditing(false);
      await load();
    } catch (p) {
      setError((p as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    if (!removing) return;
    setBusy(true);
    try {
      await api(
        active ? `${base}/artifacts/${removing}` : `${base}/notes/${removing}`,
        { method: "DELETE" },
      );
      setRemoving(null);
      setActive(null);
      setNote(null);
      await load();
    } catch (p) {
      setError((p as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const citations =
    active?.provenance.citations || note?.provenance.citations || [];
  function itemCitations(ids: string[]) {
    return citations.filter((c) => ids.includes(c.chunk_id));
  }
  return (
    <div className="studio-content">
      <div className="studio-tabs" role="tablist" aria-label="Study Studio">
        <button
          role="tab"
          aria-selected={tab === "materials"}
          onClick={() => {
            setTab("materials");
            setActive(null);
            setNote(null);
            setEditing(false);
          }}
        >
          Materials <span>{artifacts.length}</span>
        </button>
        <button
          role="tab"
          aria-selected={tab === "notes"}
          onClick={() => {
            setTab("notes");
            setActive(null);
            setNote(null);
            setEditing(false);
          }}
        >
          Notes <span>{notes.length}</span>
        </button>
      </div>
      {error && <ErrorNotice message={error} />}{" "}
      {loading && <Loading>Loading saved work…</Loading>}
      {(active || note || editing) && (
        <button
          className="back-link"
          onClick={() => {
            setActive(null);
            setNote(null);
            setEditing(false);
            setRemoving(null);
          }}
        >
          <ArrowLeft size={14} />
          Back to {tab}
        </button>
      )}
      {active ? (
        <>
          <header className="artifact-header">
            <h3>{active.title}</h3>
            <p className="muted">
              {active.kind.replaceAll("_", " ")} ·{" "}
              {active.provenance.provider_name} · {active.provenance.model}
              {" · "}
              {new Date(active.provenance.created_at).toLocaleString()} ·{" "}
              {active.provenance.source_ids.length} sources
            </p>
          </header>
          {["mindmap", "slides", "infographic"].includes(active.kind) && (
            <VisualMaterial artifact={active} openCitation={openCitation} />
          )}
          {active.kind === "quiz" &&
            active.content.questions?.map((q, i) => (
              <section className="quiz-question" key={i}>
                <h4>
                  {i + 1}. {q.question}
                </h4>
                <fieldset>
                  <legend className="visually-hidden">
                    Answer for question {i + 1}
                  </legend>
                  {q.choices?.map((choice, j) => (
                    <label
                      className={`quiz-choice${revealed.includes(i) && j === q.answer_index ? " correct" : ""}`}
                      key={j}
                    >
                      <input
                        name={`question-${i}`}
                        type="radio"
                        checked={answers[i] === j}
                        onChange={() => setAnswers({ ...answers, [i]: j })}
                      />
                      <span>
                        {String.fromCharCode(65 + j)}. {choice}
                      </span>
                    </label>
                  ))}
                </fieldset>
                <button
                  className="text-button"
                  onClick={() =>
                    setRevealed(
                      revealed.includes(i)
                        ? revealed.filter((x) => x !== i)
                        : [...revealed, i],
                    )
                  }
                >
                  {revealed.includes(i) ? "Hide explanation" : "Check answer"}
                </button>
                <button
                  className="text-button"
                  disabled={excerptSaved.includes(i)}
                  aria-label={`Save question ${i + 1} as note`}
                  onClick={() => void saveArtifact(i)}
                >
                  {excerptSaved.includes(i)
                    ? "Excerpt saved"
                    : "Save excerpt as note"}
                </button>
                {revealed.includes(i) && (
                  <div className="quiz-explanation">
                    <strong>
                      {answers[i] === undefined
                        ? `Answer: ${String.fromCharCode(65 + (q.answer_index || 0))}`
                        : answers[i] === q.answer_index
                          ? "Correct"
                          : "Try reviewing this excerpt"}
                    </strong>
                    <StudyMarkdown
                      text={q.explanation || ""}
                      citations={itemCitations(q.citations)}
                      openCitation={openCitation}
                    />
                    <CitationList
                      citations={itemCitations(q.citations)}
                      open={openCitation}
                    />
                  </div>
                )}
              </section>
            ))}
          {active.kind === "flashcards" &&
            active.content.cards?.map((c, i) => (
              <section className="flashcard" key={i}>
                <p className="eyebrow">
                  Card {i + 1} · {flipped.includes(i) ? "Answer" : "Prompt"}
                </p>
                <button
                  className="flashcard-face"
                  onClick={() =>
                    setFlipped(
                      flipped.includes(i)
                        ? flipped.filter((x) => x !== i)
                        : [...flipped, i],
                    )
                  }
                >
                  <span>{flipped.includes(i) ? c.back : c.front}</span>
                  <small>
                    {flipped.includes(i) ? "Show prompt" : "Reveal answer"}
                  </small>
                </button>
                <button
                  className="text-button"
                  disabled={excerptSaved.includes(i)}
                  aria-label={`Save card ${i + 1} as note`}
                  onClick={() => void saveArtifact(i)}
                >
                  {excerptSaved.includes(i)
                    ? "Excerpt saved"
                    : "Save excerpt as note"}
                </button>
                {flipped.includes(i) && (
                  <CitationList
                    citations={itemCitations(c.citations)}
                    open={openCitation}
                  />
                )}
              </section>
            ))}
          {(active.kind === "study_guide" || active.kind === "document") &&
            active.content.sections?.map((s, i) => (
              <section className="guide-section" key={i}>
                <h4>{s.heading}</h4>
                <button
                  className="text-button"
                  disabled={excerptSaved.includes(i)}
                  aria-label={`Save section ${i + 1} as note`}
                  onClick={() => void saveArtifact(i)}
                >
                  {excerptSaved.includes(i)
                    ? "Excerpt saved"
                    : "Save excerpt as note"}
                </button>
                <StudyMarkdown
                  text={s.body || ""}
                  citations={itemCitations(s.citations)}
                  openCitation={openCitation}
                />
                <CitationList
                  citations={itemCitations(s.citations)}
                  open={openCitation}
                />
              </section>
            ))}
          {active.kind === "spreadsheet" && (
            <div className="studio-table-scroll">
              <table className="studio-table">
                <thead>
                  <tr>
                    {active.content.columns?.map((column, i) => (
                      <th key={i} scope="col">
                        {column}
                      </th>
                    ))}
                    <th scope="col">Sources</th>
                  </tr>
                </thead>
                <tbody>
                  {active.content.rows?.map((row, i) => (
                    <tr key={i}>
                      {row.cells?.map((cell, j) => (
                        <td key={j}>{cell}</td>
                      ))}
                      <td>
                        <CitationList
                          citations={itemCitations(row.citations)}
                          open={openCitation}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="artifact-actions">
            {active.kind === "slides" && (
              <a
                className="button primary small"
                href={`${base}/artifacts/${active.id}/export?format=pptx`}
                download
              >
                <Download size={14} />
                PowerPoint (.pptx)
              </a>
            )}
            {["mindmap", "infographic"].includes(active.kind) && (
              <a
                className="button primary small"
                href={`${base}/artifacts/${active.id}/export?format=svg`}
                download
              >
                <Download size={14} />
                SVG
              </a>
            )}
            <a
              className="button secondary small"
              href={`${base}/artifacts/${active.id}/export?format=docx&template=${template}`}
              download
            >
              <Download size={14} />
              Word (.docx)
            </a>
            <a
              className="button secondary small"
              href={`${base}/artifacts/${active.id}/export?format=xlsx`}
              download
            >
              <Download size={14} />
              Excel (.xlsx)
            </a>
            <button
              className="text-button"
              disabled={saved}
              onClick={() => void saveArtifact()}
            >
              <Bookmark size={14} />
              {saved ? "Saved to notes" : "Save as note"}
            </button>
            <a
              className="text-button"
              href={`${base}/artifacts/${active.id}/export?format=markdown`}
              download
            >
              <Download size={14} />
              Markdown
            </a>
            <a
              className="text-button"
              href={`${base}/artifacts/${active.id}/export?format=json`}
              download
            >
              JSON
            </a>
            <button
              className="text-button danger-text"
              onClick={() => setRemoving(active.id)}
            >
              <Trash2 size={14} />
              Delete
            </button>
          </div>
          <details className="artifact-provenance">
            <summary>Generation details</summary>
            <p>
              Prompt {active.provenance.prompt_version}. Based on the retrieved
              excerpts at generation time; refreshing a source does not
              regenerate this material.
            </p>
            <CitationList citations={citations} open={openCitation} />
          </details>
        </>
      ) : editing ? (
        <form className="compact-form" onSubmit={(e) => void saveNote(e)}>
          <label>
            Note title
            <input
              value={title}
              maxLength={160}
              required
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>
          <label>
            Note text
            <textarea
              rows={15}
              maxLength={200000}
              value={content}
              onChange={(e) => setContent(e.target.value)}
            />
          </label>
          <button className="button primary small" disabled={busy}>
            Save note
          </button>
          <button
            type="button"
            className="text-button"
            onClick={() => setEditing(false)}
          >
            Cancel
          </button>
        </form>
      ) : note ? (
        <article className="note-view">
          <h3>{note.title}</h3>
          <StudyMarkdown
            text={note.content}
            citations={citations}
            openCitation={openCitation}
          />
          <CitationList citations={citations} open={openCitation} />
          <div className="form-actions">
            <button className="text-button" onClick={() => editNote(note)}>
              Edit note
            </button>
            <button
              className="text-button danger-text"
              onClick={() => setRemoving(note.id)}
            >
              Delete
            </button>
          </div>
        </article>
      ) : tab === "materials" ? (
        <>
          <form
            className="studio-generator compact-form"
            onSubmit={(e) => void generate(e)}
          >
            <h3>Practice from selected sources.</h3>
            <fieldset className="material-picker">
              <legend>Material</legend>
              <div className="material-buttons">
                {(
                  [
                    { value: "quiz", label: "Quiz", icon: CircleHelp },
                    { value: "flashcards", label: "Flashcards", icon: Layers },
                    {
                      value: "study_guide",
                      label: "Study guide",
                      icon: BookOpen,
                    },
                    { value: "document", label: "Word", icon: FileText },
                    { value: "spreadsheet", label: "Excel", icon: Table2 },
                    { value: "mindmap", label: "Mind map", icon: Network },
                    { value: "slides", label: "Slides", icon: Presentation },
                    {
                      value: "infographic",
                      label: "Infographic",
                      icon: ChartNoAxesCombined,
                    },
                  ] as const
                ).map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    aria-pressed={kind === option.value}
                    disabled={busy}
                    onClick={() => {
                      setKind(option.value);
                      if (option.value === "infographic")
                        setCount(Math.min(count, 6));
                    }}
                  >
                    <option.icon size={19} aria-hidden="true" />
                    {option.label}
                  </button>
                ))}
              </div>
            </fieldset>
            {["mindmap", "slides", "infographic"].includes(kind) && (
              <label>
                Language
                <select
                  value={language}
                  onChange={(event) => setLanguage(event.target.value)}
                  disabled={busy}
                >
                  <option value="automatic">Source language</option>
                  <option value="en">English</option>
                  <option value="zh-Hant">繁體中文</option>
                  <option value="zh-Hans">简体中文</option>
                </select>
              </label>
            )}
            {kind === "slides" && (
              <fieldset className="segmented-picker">
                <legend>Presentation format</legend>
                <div>
                  {[
                    {
                      value: "detailed",
                      label: "Detailed deck",
                      help: "Readable without a speaker",
                    },
                    {
                      value: "presenter",
                      label: "Presenter slides",
                      help: "Brief slides with speaker notes",
                    },
                  ].map((option) => (
                    <button
                      type="button"
                      key={option.value}
                      aria-pressed={slideFormat === option.value}
                      disabled={busy}
                      onClick={() => setSlideFormat(option.value)}
                    >
                      <strong>{option.label}</strong>
                      <small>{option.help}</small>
                    </button>
                  ))}
                </div>
              </fieldset>
            )}
            {kind === "infographic" && (
              <>
                <fieldset className="segmented-picker">
                  <legend>Orientation</legend>
                  <div>
                    {["landscape", "portrait", "square"].map((value) => (
                      <button
                        type="button"
                        key={value}
                        aria-pressed={orientation === value}
                        disabled={busy}
                        onClick={() => setOrientation(value)}
                      >
                        {value}
                      </button>
                    ))}
                  </div>
                </fieldset>
                <fieldset className="segmented-picker">
                  <legend>Visual style</legend>
                  <div>
                    {[
                      "automatic",
                      "editorial",
                      "bold",
                      "notebook",
                      "playful",
                    ].map((value) => (
                      <button
                        type="button"
                        key={value}
                        aria-pressed={visualStyle === value}
                        disabled={busy}
                        onClick={() => setVisualStyle(value)}
                      >
                        {value}
                      </button>
                    ))}
                  </div>
                </fieldset>
                <p className="muted">
                  A vector layout with source-backed text and statistics. Export
                  as SVG for a scalable graphic.
                </p>
              </>
            )}
            {kind === "document" && (
              <label>
                Document template
                <small>
                  Choose a layout style, or let the model select based on the
                  content.
                </small>
                <select
                  value={template}
                  onChange={(event) => setTemplate(event.target.value)}
                  disabled={busy}
                >
                  <option value="automatic">Automatic</option>
                  <option value="study_notes">
                    Study notes · Easy reading
                  </option>
                  <option value="revision_outline">
                    Revision outline · Compact
                  </option>
                  <option value="analysis_report">
                    Analysis report · Professional
                  </option>
                </select>
              </label>
            )}
            <label>
              Topic or focus
              <input
                value={topic}
                maxLength={1000}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="Leave blank for selected material"
              />
            </label>
            <label>
              Instructions
              <textarea
                rows={3}
                maxLength={6000}
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                placeholder="Describe what to create, the language, or points to focus on…"
                disabled={busy}
              />
            </label>
            <div className="item-count-row">
              <label>
                {kind === "quiz"
                  ? "Questions"
                  : kind === "flashcards"
                    ? "Cards"
                    : kind === "mindmap"
                      ? "Concepts"
                      : kind === "slides"
                        ? "Slides"
                        : kind === "spreadsheet"
                          ? "Rows"
                          : "Sections"}
                <input
                  type="number"
                  value={count}
                  min={1}
                  max={kind === "infographic" ? 6 : 20}
                  required
                  onChange={(e) => setCount(Number(e.target.value))}
                />
              </label>
            </div>
            <label className="difficulty-control">
              <span>
                Difficulty{" "}
                <strong>
                  {
                    difficultyLabels[
                      difficulties.indexOf(
                        difficulty as (typeof difficulties)[number],
                      )
                    ]
                  }
                </strong>
              </span>
              <input
                type="range"
                aria-label="Difficulty"
                min={0}
                max={2}
                step={1}
                value={difficulties.indexOf(
                  difficulty as (typeof difficulties)[number],
                )}
                aria-valuetext={
                  difficultyLabels[
                    difficulties.indexOf(
                      difficulty as (typeof difficulties)[number],
                    )
                  ]
                }
                disabled={busy}
                onChange={(event) =>
                  setDifficulty(difficulties[Number(event.target.value)])
                }
              />
              <span className="difficulty-scale" aria-hidden="true">
                <span>Introductory</span>
                <span>Intermediate</span>
                <span>Advanced</span>
              </span>
            </label>
            <p className="muted">
              {sourceIds.length} selected sources ·{" "}
              {provider
                ? `${provider.name} (${provider.model})`
                : "Choose a provider in the conversation panel"}
              . Uses excerpts from your selected sources.
            </p>
            <button
              className="button primary"
              disabled={busy || !sourceIds.length || !providerId}
            >
              {busy ? "Generating and validating…" : "Generate material"}
            </button>
            {!providerId && (
              <p className="muted">
                Choose a provider in the conversation panel first.
              </p>
            )}
          </form>
          <div className="studio-saved">
            <h3>Saved materials</h3>
            {artifacts.length ? (
              artifacts.map((a) => (
                <button
                  className="saved-item"
                  key={a.id}
                  onClick={() => openArtifact(a)}
                >
                  <span>{a.title}</span>
                  <small>
                    {a.kind.replaceAll("_", " ")} ·{" "}
                    {new Date(a.provenance.created_at).toLocaleDateString()}
                  </small>
                </button>
              ))
            ) : (
              <p className="muted">
                Your generated practice materials will be saved here with their
                sources.
              </p>
            )}
          </div>
        </>
      ) : (
        <>
          <button className="button secondary small" onClick={() => editNote()}>
            <Plus size={15} />
            New note
          </button>
          <div className="studio-saved">
            {notes.map((n) => (
              <button
                className="saved-item"
                key={n.id}
                onClick={() => {
                  setNote(n);
                  setActive(null);
                  setEditing(false);
                  setRemoving(null);
                }}
              >
                <span>{n.title}</span>
                <small>
                  Updated {new Date(n.updated_at).toLocaleDateString()}
                </small>
              </button>
            ))}
            {!notes.length && (
              <p className="muted">
                Write a note here or save an assistant answer. Notes are never
                uploaded to Canvas automatically.
              </p>
            )}
          </div>
        </>
      )}
      {removing && (
        <div className="inline-confirm">
          <p>
            Delete this saved {active ? "material" : "note"} from your
            workspace?
          </p>
          <button
            className="button danger small"
            disabled={busy}
            onClick={() => void remove()}
          >
            Delete
          </button>
          <button className="text-button" onClick={() => setRemoving(null)}>
            Keep it
          </button>
        </div>
      )}
    </div>
  );
}
