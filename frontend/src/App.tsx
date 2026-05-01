import type { JSX } from "react";
import { Link, Navigate, NavLink, Route, Routes, useNavigate } from "react-router-dom";

import Accounts from "./pages/Accounts";
import DraftDetail from "./pages/DraftDetail";
import Drafts from "./pages/Drafts";
import Library from "./pages/Library";
import Login from "./pages/Login";
import Settings from "./pages/Settings";

function isAuthed(): boolean {
  return Boolean(localStorage.getItem("token"));
}

function RequireAuth({ children }: { children: JSX.Element }) {
  return isAuthed() ? children : <Navigate to="/login" replace />;
}

const NAV_LINKS = [
  { to: "/library", label: "素材库" },
  { to: "/drafts", label: "草稿" },
  { to: "/accounts", label: "公众号" },
  { to: "/settings", label: "设置" },
];

function Nav() {
  const navigate = useNavigate();

  function handleLogout() {
    localStorage.removeItem("token");
    navigate("/login");
  }

  return (
    <header
      style={{
        height: "var(--nav-height)",
        borderBottom: "1px solid var(--color-surface-3)",
        backgroundColor: "var(--color-white)",
        position: "sticky",
        top: 0,
        zIndex: 40,
      }}
    >
      <div
        style={{
          maxWidth: "var(--max-content)",
          margin: "0 auto",
          height: "100%",
          display: "flex",
          alignItems: "center",
          gap: "var(--space-6)",
          padding: "0 var(--space-8)",
        }}
      >
        {/* Logo mark */}
        <Link
          to="/library"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--space-2)",
            textDecoration: "none",
            flexShrink: 0,
          }}
        >
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: "28px",
              height: "28px",
              borderRadius: "var(--radius-sm)",
              backgroundColor: "var(--color-ink)",
              color: "var(--color-accent-fg)",
              fontSize: "13px",
              fontWeight: "var(--weight-semi)",
              letterSpacing: "-0.5px",
              flexShrink: 0,
            }}
          >
            微
          </span>
          <span
            style={{
              fontSize: "var(--text-sm)",
              fontWeight: "var(--weight-semi)",
              color: "var(--color-ink)",
              letterSpacing: "-0.2px",
            }}
          >
            批量改写
          </span>
        </Link>

        {/* Divider */}
        <div
          style={{
            width: "1px",
            height: "18px",
            backgroundColor: "var(--color-surface-3)",
            flexShrink: 0,
          }}
        />

        {/* Nav links */}
        <nav aria-label="主导航" style={{ display: "flex", alignItems: "center", gap: "var(--space-1)", flex: 1 }}>
          {NAV_LINKS.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              style={({ isActive }) => ({
                display: "inline-flex",
                alignItems: "center",
                height: "var(--nav-height)",
                padding: "0 var(--space-3)",
                fontSize: "var(--text-sm)",
                fontWeight: isActive ? "var(--weight-medium)" : "var(--weight-normal)",
                color: isActive ? "var(--color-ink)" : "var(--color-ink-3)",
                textDecoration: "none",
                borderBottom: isActive ? "2px solid var(--color-ink)" : "2px solid transparent",
                transition: `color var(--dur-fast), border-color var(--dur-fast)`,
                marginBottom: "-1px", // align with header bottom border
              })}
            >
              {label}
            </NavLink>
          ))}
        </nav>

        {/* User menu */}
        <button
          onClick={handleLogout}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "var(--space-2)",
            padding: "var(--space-1) var(--space-3)",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--color-surface-3)",
            backgroundColor: "transparent",
            color: "var(--color-ink-2)",
            fontSize: "var(--text-sm)",
            cursor: "pointer",
            transition: `background-color var(--dur-fast), color var(--dur-fast)`,
            flexShrink: 0,
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.backgroundColor = "var(--color-surface-2)";
            (e.currentTarget as HTMLButtonElement).style.color = "var(--color-ink)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.backgroundColor = "transparent";
            (e.currentTarget as HTMLButtonElement).style.color = "var(--color-ink-2)";
          }}
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
            <circle cx="7" cy="4.5" r="2.5" stroke="currentColor" strokeWidth="1.25" />
            <path d="M2 12c0-2.5 2.2-4 5-4s5 1.5 5 4" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
          </svg>
          退出
        </button>
      </div>
    </header>
  );
}

function Shell({ children }: { children: JSX.Element }) {
  return (
    <RequireAuth>
      <>
        <Nav />
        <main style={{ minHeight: "calc(100vh - var(--nav-height))" }}>
          {children}
        </main>
      </>
    </RequireAuth>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/library"
        element={
          <Shell>
            <Library />
          </Shell>
        }
      />
      <Route
        path="/drafts"
        element={
          <Shell>
            <Drafts />
          </Shell>
        }
      />
      <Route
        path="/drafts/:id"
        element={
          <Shell>
            <DraftDetail />
          </Shell>
        }
      />
      <Route
        path="/accounts"
        element={
          <Shell>
            <Accounts />
          </Shell>
        }
      />
      <Route
        path="/settings"
        element={
          <Shell>
            <Settings />
          </Shell>
        }
      />
      <Route path="*" element={<Navigate to="/library" replace />} />
    </Routes>
  );
}
