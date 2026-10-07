import { createElement, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { X, ArrowUpRight } from "lucide-react";
import { api } from "../api";
import { ErrorNotice, Loading } from "../components";
import type { Citation, Chunk, Source } from "../types";

export function locatorLabel(locator: Record<string, string | number>) {
  return Object.entries(locator)
    .filter(([key, value]) => key !== "offset" && value !== "")
    .map(([key, value]) => `${key[0].toUpperCase() + key.slice(1)} ${value}`)
    .join(" · ");
}

export function CanvasSourceBody({ html }: { html: string }) {
  const content = useMemo(() => {
    const document = new DOMParser().parseFromString(html, "text/html");
    function render(node: Node, key: string, depth = 0): ReactNode {
      if (node.nodeType === Node.TEXT_NODE || depth > 40)
        return node.textContent;
      if (!(node instanceof Element)) return null;
      const style: Record<string, string> = {};
      // DOMParser can discard CSS declarations under the app's strict CSP.
      // Read the server-sanitized attribute and apply it through React's CSSOM.
      for (const declaration of (node.getAttribute("style") || "").split(";")) {
        const separator = declaration.indexOf(":");
        if (separator < 1) continue;
        const property = declaration.slice(0, separator).trim();
        const value = declaration.slice(separator + 1).trim();
        if (property && value)
          style[
            property.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase())
          ] = value;
      }
      const props: Record<string, unknown> = {
        key,
        style: style as CSSProperties,
      };
      for (const [attribute, property] of Object.entries({
        href: "href",
        target: "target",
        rel: "rel",
        referrerpolicy: "referrerPolicy",
        dir: "dir",
        colspan: "colSpan",
        rowspan: "rowSpan",
        start: "start",
        class: "className",
      }))
        if (node.hasAttribute(attribute))
          props[property] = node.getAttribute(attribute);
      const children = Array.from(node.childNodes).map((child, index) =>
        render(child, `${key}.${index}`, depth + 1),
      );
      const tag = node.tagName.toLowerCase();
      return createElement(
        tag,
        props,
        ...(["br", "hr", "col"].includes(tag) ? [] : children),
      );
    }
    return Array.from(document.body.childNodes).map((node, index) =>
      render(node, String(index)),
    );
  }, [html]);
  return <div className="canvas-source-body">{content}</div>;
}

export function StudyMarkdown({
  text,
  citations = [],
  openCitation,
}: {
  text: string;
  citations?: Citation[];
  openCitation: (citation: Citation) => void;
}) {
  const rendered = text.replace(/\[cite:([^\]\s]+)\]/g, (_match, id) =>
    citations.some((c) => c.chunk_id === id)
      ? `[Source ${citations.findIndex((c) => c.chunk_id === id) + 1}](#citation-${id})`
      : "[citation pending verification]",
  );
  return (
    <div className="study-markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        components={{
          a: ({ href, children }) => {
            if (href?.startsWith("#citation-")) {
              const citation = citations.find(
                (c) => c.chunk_id === href.slice(10),
              );
              return citation ? (
                <button
                  className="citation-inline"
                  onClick={() => openCitation(citation)}
                >
                  {children}
                </button>
              ) : (
                <span>{children}</span>
              );
            }
            // Only explicit HTTP(S) links are actionable; HTML is never interpreted.
            return href && /^https?:\/\//i.test(href) ? (
              <a href={href} target="_blank" rel="noopener noreferrer">
                {children}
              </a>
            ) : (
              <span>{children}</span>
            );
          },
          img: () => (
            <span className="muted">
              [Image omitted; open the source to view it]
            </span>
          ),
          // Model-inserted hard line breaks in prose must follow the panel width.
          // Code and user prompts keep their original whitespace separately.
          br: () => <> </>,
        }}
      >
        {rendered}
      </ReactMarkdown>
    </div>
  );
}

export function CitationList({
  citations,
  open,
}: {
  citations: Citation[];
  open: (c: Citation) => void;
}) {
  return citations.length ? (
    <div className="citation-list" aria-label="Verified source citations">
      {citations.map((c, i) => (
        <button
          key={c.chunk_id}
          className="citation-button"
          onClick={() => open(c)}
        >
          <span>{i + 1}</span>
          {c.title}
          <small>{locatorLabel(c.locator)}</small>
        </button>
      ))}
    </div>
  ) : null;
}

export function SourceViewer({
  workspaceId,
  sourceId,
  citation,
  close,
}: {
  workspaceId: string;
  sourceId?: string;
  citation?: Citation;
  close: () => void;
}) {
  const [source, setSource] = useState<Source | null>(null),
    [chunks, setChunks] = useState<Chunk[]>([]),
    [total, setTotal] = useState(0),
    [displayHtml, setDisplayHtml] = useState<string | null>(null),
    [displayText, setDisplayText] = useState<string | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(true);
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    panel.current?.querySelector<HTMLButtonElement>("button")?.focus();
    function key(event: KeyboardEvent) {
      if (event.key === "Escape") close();
      if (event.key === "Tab" && panel.current) {
        const items = panel.current.querySelectorAll<HTMLElement>(
          "button:not(:disabled), a[href], [tabindex='0']",
        );
        const first = items[0],
          last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    }
    document.addEventListener("keydown", key);
    void (async () => {
      try {
        if (citation) {
          const chunk = await api<Chunk>(
            `/api/workspaces/${workspaceId}/citations/${citation.chunk_id}`,
          );
          setChunks([chunk]);
          setTotal(1);
        } else {
          const result = await api<{
            source: Source;
            chunks: Chunk[];
            total_chunks: number;
            display_html?: string | null;
            display_text?: string;
          }>(`/api/workspaces/${workspaceId}/sources/${sourceId}`);
          setSource(result.source);
          setChunks(result.chunks);
          setTotal(result.total_chunks);
          setDisplayHtml(result.display_html || null);
          setDisplayText(result.display_text || null);
        }
      } catch (problem) {
        setError((problem as Error).message);
      } finally {
        setBusy(false);
      }
    })();
    return () => {
      document.removeEventListener("keydown", key);
      previous?.focus();
    };
  }, [workspaceId, sourceId, citation]);
  async function more() {
    setBusy(true);
    try {
      const r = await api<{ chunks: Chunk[] }>(
        `/api/workspaces/${workspaceId}/sources/${sourceId}?offset=${chunks.length}`,
      );
      setChunks([...chunks, ...r.chunks]);
    } catch (p) {
      setError((p as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const url = source?.canvas_url || citation?.canvas_url;
  return (
    <div className="dialog-backdrop" onClick={close}>
      <div
        className="source-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="source-viewer-title"
        ref={panel}
        onClick={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <h2 id="source-viewer-title">
              {source?.title || citation?.title || "Opening source…"}
            </h2>
          </div>
          <button
            className="icon-button"
            aria-label="Close source"
            onClick={close}
          >
            <X size={20} />
          </button>
        </header>
        {url && /^https:\/\/canvas\.ust\.hk\//.test(url) && (
          <a
            className="external-link"
            href={
              url +
              (citation?.locator.page ? `#page=${citation.locator.page}` : "")
            }
            target="_blank"
            rel="noopener noreferrer"
          >
            Open in Canvas <ArrowUpRight size={16} />
          </a>
        )}
        {source && (
          <p className="muted">
            {source.status.replaceAll("_", " ")} ·{" "}
            {source.last_sync_at
              ? `Synced ${new Date(source.last_sync_at).toLocaleString()}`
              : "Not yet synced"}
          </p>
        )}
        {error && <ErrorNotice message={error} />}
        {error && citation && (
          <blockquote>
            <p>{citation.excerpt}</p>
            <small>Saved excerpt · {locatorLabel(citation.locator)}</small>
          </blockquote>
        )}
        {displayHtml ? (
          <CanvasSourceBody html={displayHtml} />
        ) : displayText ? (
          <div className="source-reading-text">{displayText}</div>
        ) : (
          chunks.map((c) => (
            <section className="source-chunk" key={c.id}>
              <h3>{locatorLabel(c.locator) || "Text excerpt"}</h3>
              <p>{c.text}</p>
            </section>
          ))
        )}
        {source?.metadata.external_url && (
          <a
            className="external-link"
            href={source.metadata.external_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            Open external reference <ArrowUpRight size={16} />
          </a>
        )}
        {source?.status === "external_reference" && (
          <p>
            External tools and videos are kept as links. Their authenticated
            content is not downloaded. Upload a caption file to study a video.
          </p>
        )}
        {!busy && !chunks.length && !error && (
          <p>
            {source?.error_message ||
              "Sync this source to inspect its extracted text."}
          </p>
        )}
        {busy && <Loading>Reading source…</Loading>}
        {!displayHtml && !displayText && !busy && chunks.length < total && (
          <button className="button secondary" onClick={() => void more()}>
            Load more excerpts ({chunks.length}/{total})
          </button>
        )}
      </div>
    </div>
  );
}
