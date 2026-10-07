import { useRef } from "react";
import type { KeyboardEvent } from "react";

export function PanelResizeHandle({
  side,
  size,
  minimum,
  maximum,
  disabled,
  controls,
  onResize,
  onReset,
}: {
  side: "sources" | "studio";
  size: number;
  minimum: number;
  maximum: number;
  disabled: boolean;
  controls: string;
  onResize: (size: number) => void;
  onReset: () => void;
}) {
  const drag = useRef<{ x: number; size: number } | null>(null);
  const direction = side === "sources" ? 1 : -1;
  function keyboard(event: KeyboardEvent<HTMLDivElement>) {
    if (disabled) return;
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault();
      onResize(size + (event.key === "ArrowRight" ? 24 : -24) * direction);
    } else if (event.key === "Home" || event.key === "End") {
      event.preventDefault();
      onResize(event.key === "Home" ? minimum : maximum);
    }
  }
  return (
    <div
      className={`panel-resize-handle${disabled ? " inactive" : ""}`}
      role="separator"
      tabIndex={disabled ? -1 : 0}
      aria-label={
        side === "sources"
          ? "Resize Sources and Conversation"
          : "Resize Conversation and Study Studio"
      }
      aria-orientation="vertical"
      aria-controls={controls}
      aria-valuemin={Math.round(minimum)}
      aria-valuemax={Math.round(maximum)}
      aria-valuenow={Math.round(size)}
      aria-valuetext={`${Math.round(size)} pixels`}
      aria-disabled={disabled}
      title="Drag to resize · Arrow keys to adjust · Double-click to reset"
      onKeyDown={keyboard}
      onDoubleClick={onReset}
      onPointerDown={(event) => {
        if (disabled || event.button !== 0) return;
        event.preventDefault();
        event.currentTarget.focus();
        drag.current = { x: event.clientX, size };
        event.currentTarget.setPointerCapture(event.pointerId);
        event.currentTarget.dataset.dragging = "true";
      }}
      onPointerMove={(event) => {
        if (drag.current)
          onResize(
            drag.current.size + (event.clientX - drag.current.x) * direction,
          );
      }}
      onPointerUp={(event) => {
        drag.current = null;
        delete event.currentTarget.dataset.dragging;
        if (event.currentTarget.hasPointerCapture(event.pointerId))
          event.currentTarget.releasePointerCapture(event.pointerId);
      }}
      onLostPointerCapture={(event) => {
        drag.current = null;
        delete event.currentTarget.dataset.dragging;
      }}
      onPointerCancel={(event) => {
        drag.current = null;
        delete event.currentTarget.dataset.dragging;
      }}
    >
      <span aria-hidden="true" />
    </div>
  );
}
