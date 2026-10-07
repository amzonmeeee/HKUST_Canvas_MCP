import { useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Expand, X } from "lucide-react";
import type { Artifact, ArtifactItem, Citation } from "../types";
import { CitationList, StudyMarkdown } from "./StudyContent";

export function VisualMaterial({
  artifact,
  openCitation,
}: {
  artifact: Artifact;
  openCitation: (citation: Citation) => void;
}) {
  const [slide, setSlide] = useState(0);
  const dialog = useRef<HTMLDialogElement>(null);
  const inspectCitation = (citation: Citation) => {
    if (dialog.current?.open) dialog.current.close();
    openCitation(citation);
  };
  const refs = (item: ArtifactItem) =>
    artifact.provenance.citations.filter((c) =>
      item.citations.includes(c.chunk_id),
    );
  function node(item: ArtifactItem, depth = 0): React.ReactNode {
    if (depth > 20) return null;
    const children =
      artifact.content.nodes?.filter((n) => n.parent_id === item.id) || [];
    return (
      <li key={item.id}>
        <details open>
          <summary>{item.label}</summary>
          <p>{item.body}</p>
          <CitationList citations={refs(item)} open={inspectCitation} />
          {children.length > 0 && (
            <ul>{children.map((n) => node(n, depth + 1))}</ul>
          )}
        </details>
      </li>
    );
  }
  function content() {
    if (artifact.kind === "mindmap")
      return (
        <div className="mindmap-preview">
          <h4>{artifact.title}</h4>
          <ul className="mindmap-tree">
            {artifact.content.nodes
              ?.filter((n) => !n.parent_id)
              .map((n) => node(n))}
          </ul>
        </div>
      );
    if (artifact.kind === "infographic")
      return (
        <div
          className={`infographic-preview orientation-${artifact.provenance.orientation || "landscape"} visual-${artifact.provenance.visual_style || "editorial"}`}
        >
          <h4>{artifact.title}</h4>
          <div className="infographic-sections">
            {artifact.content.sections?.map((item, i) => (
              <section key={i}>
                <h5>{item.heading}</h5>
                {item.stat && (
                  <strong className="infographic-stat">{item.stat}</strong>
                )}
                <p>{item.body}</p>
                <CitationList citations={refs(item)} open={inspectCitation} />
              </section>
            ))}
          </div>
        </div>
      );
    const slides = artifact.content.slides || [],
      item = slides[slide];
    return item ? (
      <div className="slides-preview">
        <div className="slide-navigation">
          <button
            className="icon-button"
            aria-label="Previous slide"
            disabled={slide === 0}
            onClick={() => setSlide(slide - 1)}
          >
            <ChevronLeft size={18} />
          </button>
          <span>
            Slide {slide + 1} of {slides.length}
          </span>
          <button
            className="icon-button"
            aria-label="Next slide"
            disabled={slide === slides.length - 1}
            onClick={() => setSlide(slide + 1)}
          >
            <ChevronRight size={18} />
          </button>
        </div>
        <article className="presentation-slide">
          <h4>{item.heading}</h4>
          {item.body && <p>{item.body}</p>}
          <ul>
            {item.bullets?.map((b, i) => (
              <li key={i}>{b}</li>
            ))}
          </ul>
          <CitationList citations={refs(item)} open={inspectCitation} />
        </article>
        <details className="speaker-notes">
          <summary>Speaker notes</summary>
          <StudyMarkdown
            text={item.notes || ""}
            citations={refs(item)}
            openCitation={inspectCitation}
          />
        </details>
      </div>
    ) : null;
  }
  return (
    <div className="visual-material">
      <button
        className="text-button"
        onClick={() => dialog.current?.showModal()}
      >
        <Expand size={15} />
        Expand preview
      </button>
      {content()}
      <dialog
        ref={dialog}
        aria-label={`${artifact.kind.replaceAll("_", " ")} preview: ${artifact.title}`}
        className="visual-material-dialog"
        onClick={(event) => {
          if (event.target === event.currentTarget) dialog.current?.close();
        }}
      >
        <header>
          <h3>{artifact.title}</h3>
          <button
            className="icon-button"
            aria-label="Close material preview"
            onClick={() => dialog.current?.close()}
          >
            <X size={18} />
          </button>
        </header>
        {content()}
      </dialog>
    </div>
  );
}
