import { Logo } from "./Logo";
import { useEffect, useState } from "react";
import {
  LayoutDashboard,
  Settings as SettingsIcon,
  ArrowLeft,
  ArrowUpRight,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import { initializeSession } from "./api";
import { ErrorNotice, Loading } from "./components";
import { Dashboard } from "./features/Dashboard";
import { WorkspacePage } from "./features/Workspace";
import { SettingsPage } from "./features/Settings";

export function App() {
  const [path, setPath] = useState(window.location.pathname);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [collapsed, setCollapsed] = useState(false);
  useEffect(() => {
    let active = true;
    initializeSession()
      .then(() => {
        if (active) setReady(true);
      })
      .catch(() => {
        if (active)
          setError(
            "This session has ended or needs its launch link. Open the URL printed by canvas web.",
          );
      });
    const pop = () => setPath(window.location.pathname);
    window.addEventListener("popstate", pop);
    return () => {
      active = false;
      window.removeEventListener("popstate", pop);
    };
  }, []);
  function navigate(target: string) {
    window.history.pushState(null, "", target);
    setPath(target);
    window.scrollTo({ top: 0 });
  }
  const workspaceId = path.match(/^\/workspace\/([0-9a-f-]+)$/i)?.[1];
  const dashboard = path === "/";
  const settings = path === "/settings";
  return (
    <div className={`app-shell${collapsed ? " rail-collapsed" : ""}`}>
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <aside className="nav-rail" aria-label="Main navigation">
        <button
          className="brand"
          onClick={() => navigate("/")}
          aria-label="HKUST Canvas Workbench home"
        >
          <Logo />
          <span>
            Canvas
            <br />
            <strong>Workbench</strong>
          </span>
        </button>

        <nav>
          <button
            aria-label="Dashboard"
            title="Dashboard"
            className={`nav-item${dashboard || workspaceId ? " active" : ""}`}
            aria-current={dashboard || workspaceId ? "page" : undefined}
            onClick={() => navigate("/")}
          >
            <LayoutDashboard size={19} aria-hidden="true" />
            <span>Dashboard</span>
          </button>
          <button
            aria-label="Settings"
            title="Settings"
            className={`nav-item${settings ? " active" : ""}`}
            aria-current={settings ? "page" : undefined}
            onClick={() => navigate("/settings")}
          >
            <SettingsIcon size={19} aria-hidden="true" />
            <span>Settings</span>
          </button>
        </nav>
        <div className="rail-footer">
          <p>
            Your courses.
            <br />
            Your workspace.
            <br />
            Your data stays under your control.
          </p>
          <a
            href="https://canvas.ust.hk"
            target="_blank"
            rel="noopener noreferrer"
          >
            HKUST Canvas
            <ArrowUpRight size={15} aria-hidden="true" />
          </a>
        </div>
        <button
          className="rail-toggle"
          onClick={() => setCollapsed(!collapsed)}
          aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
        >
          {collapsed ? (
            <PanelLeftOpen size={18} />
          ) : (
            <PanelLeftClose size={18} />
          )}
        </button>
      </aside>
      <main
        id="main"
        className={`main-content${workspaceId ? " workspace-page" : ""}`}
        tabIndex={-1}
      >
        {!ready ? (
          <div className="session-screen">
            <h1>Canvas Workbench</h1>
            {error ? (
              <ErrorNotice message={error} />
            ) : (
              <Loading>Connecting to your workbench…</Loading>
            )}
          </div>
        ) : dashboard ? (
          <Dashboard navigate={navigate} />
        ) : settings ? (
          <SettingsPage />
        ) : workspaceId ? (
          <WorkspacePage
            key={workspaceId}
            workspaceId={workspaceId}
            navigate={navigate}
          />
        ) : (
          <div className="session-screen">
            <h1>Page not found</h1>
            <button className="button" onClick={() => navigate("/")}>
              <ArrowLeft size={16} />
              Back to dashboard
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
