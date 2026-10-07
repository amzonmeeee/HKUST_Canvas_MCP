import { useEffect, useState } from "react";
import type { CSSProperties } from "react";

const STORAGE_KEY = "canvas-workbench.panel-widths.v1";
const DEFAULTS = { sources: 0.24, studio: 0.28 };
export type PanelSide = "sources" | "studio";

function savedWidths() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    if (
      saved &&
      Number.isFinite(saved.sources) &&
      Number.isFinite(saved.studio) &&
      saved.sources > 0 &&
      saved.sources < 1 &&
      saved.studio > 0 &&
      saved.studio < 1
    )
      return saved as typeof DEFAULTS;
  } catch {
    /* Layout remains usable when browser storage is unavailable. */
  }
  return DEFAULTS;
}

export function usePanelLayout(sourcesOpen: boolean, studioOpen: boolean) {
  const [container, setContainer] = useState<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(0);
  const [ratios, setRatios] = useState(savedWidths);
  useEffect(() => {
    const element = container;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) =>
      setWidth(entry.contentRect.width),
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [container]);
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(ratios));
    } catch {
      /* Optional preference. */
    }
  }, [ratios]);
  const minimum = {
    sources: sourcesOpen ? 240 : 56,
    studio: studioOpen ? 280 : 56,
  };
  const sideSpace = Math.max(minimum.sources + minimum.studio, width - 380);
  const sizes = {
    sources: Math.max(
      minimum.sources,
      Math.min(width * ratios.sources, sideSpace - minimum.studio),
    ),
    studio: minimum.studio,
  };
  if (!sourcesOpen) sizes.sources = minimum.sources;
  if (studioOpen)
    sizes.studio = Math.max(
      minimum.studio,
      Math.min(width * ratios.studio, sideSpace - sizes.sources),
    );
  const maximum = {
    sources: Math.max(minimum.sources, sideSpace - sizes.studio),
    studio: Math.max(minimum.studio, sideSpace - sizes.sources),
  };
  function resize(side: PanelSide, pixels: number) {
    if (!width) return;
    const value = Math.max(minimum[side], Math.min(pixels, maximum[side]));
    setRatios((previous) => ({ ...previous, [side]: value / width }));
  }
  const style = {
    "--sources-width": width ? `${sizes.sources}px` : "24%",
    "--studio-width": width ? `${sizes.studio}px` : "28%",
  } as CSSProperties;
  return {
    container: setContainer,
    style,
    sizes,
    minimum,
    maximum,
    resize,
    reset: () => setRatios(DEFAULTS),
  };
}
