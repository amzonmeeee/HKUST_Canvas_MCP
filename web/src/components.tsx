import { ArrowUpRight, AlertCircle, LoaderCircle } from "lucide-react";
import type { ReactNode } from "react";

export function ErrorNotice({
  message,
  retry,
}: {
  message: string;
  retry?: () => void;
}) {
  return (
    <div className="error-notice" role="alert">
      <AlertCircle size={18} aria-hidden="true" />
      <div>
        <p>{message}</p>
        {retry && (
          <button className="text-button" onClick={retry}>
            Retry
          </button>
        )}
      </div>
    </div>
  );
}

export function Loading({ children = "Loading…" }: { children?: ReactNode }) {
  return (
    <div className="loading" role="status">
      <LoaderCircle size={18} aria-hidden="true" />
      {children}
    </div>
  );
}

export function CanvasLink({ courseId }: { courseId?: string | null }) {
  const href = courseId
    ? `https://canvas.ust.hk/courses/${encodeURIComponent(courseId)}`
    : "https://canvas.ust.hk";
  return (
    <a
      className="external-link"
      href={href}
      target="_blank"
      rel="noopener noreferrer"
    >
      Open Canvas
      <ArrowUpRight size={15} aria-hidden="true" />
    </a>
  );
}

export function EmptyState({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="empty-state">
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
