import type { JSX, ReactNode } from "react";
import { Link, Navigate, NavLink, Route, Routes, useNavigate } from "react-router-dom";

import Accounts from "./pages/Accounts";
import DraftDetail from "./pages/DraftDetail";
import Drafts from "./pages/Drafts";
import ImageAssets from "./pages/ImageAssets";
import ImagePostDetail from "./pages/ImagePostDetail";
import ImagePosts from "./pages/ImagePosts";
import Library from "./pages/Library";
import Login from "./pages/Login";
import Settings from "./pages/Settings";

function isAuthed(): boolean {
  return Boolean(localStorage.getItem("token"));
}

function RequireAuth({ children }: { children: JSX.Element }) {
  return isAuthed() ? children : <Navigate to="/login" replace />;
}

interface NavItem {
  to: string;
  label: string;
  icon: ReactNode;
}

const NAV_PRIMARY: NavItem[] = [
  {
    to: "/library",
    label: "素材库",
    icon: (
      <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path d="M3 4h10M3 8h10M3 12h6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    to: "/drafts",
    label: "草稿",
    icon: (
      <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path d="M4 2h6l3 3v9H4V2z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
        <path d="M10 2v3h3" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    to: "/image-posts",
    label: "图片",
    icon: (
      <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <rect x="2" y="2" width="12" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="5.5" cy="5.5" r="1" fill="currentColor" />
        <path d="M2 11l3.5-3.5L8 10l2.5-2.5L14 11" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      </svg>
    ),
  },
];

const NAV_SECONDARY: NavItem[] = [
  {
    to: "/accounts",
    label: "公众号",
    icon: (
      <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <circle cx="8" cy="6" r="2.5" stroke="currentColor" strokeWidth="1.5" />
        <path d="M3 14c0-2.5 2.2-4.5 5-4.5s5 2 5 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    to: "/settings",
    label: "设置",
    icon: (
      <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.5" />
        <path
          d="M8 1.5v1.8M8 12.7v1.8M14.5 8h-1.8M3.3 8H1.5M12.6 3.4l-1.3 1.3M4.7 11.3l-1.3 1.3M12.6 12.6l-1.3-1.3M4.7 4.7L3.4 3.4"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      </svg>
    ),
  },
];

function Sidebar() {
  const navigate = useNavigate();

  function handleLogout() {
    localStorage.removeItem("token");
    navigate("/login");
  }

  return (
    <aside className="sidebar" aria-label="主导航">
      <Link to="/library" className="sidebar-brand">
        <span className="sidebar-brand-mark">微</span>
        <span className="sidebar-brand-text">批量改写</span>
      </Link>

      <nav className="sidebar-section" aria-label="工作台">
        <span className="sidebar-section-label">工作台</span>
        {NAV_PRIMARY.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => `sidebar-link${isActive ? " is-active" : ""}`}
          >
            {icon}
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <nav className="sidebar-section" aria-label="管理">
        <span className="sidebar-section-label">管理</span>
        {NAV_SECONDARY.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => `sidebar-link${isActive ? " is-active" : ""}`}
          >
            {icon}
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <button onClick={handleLogout} className="sidebar-user" aria-label="退出登录">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
            <circle cx="7" cy="4.5" r="2.5" stroke="currentColor" strokeWidth="1.25" />
            <path d="M2 12c0-2.5 2.2-4 5-4s5 1.5 5 4" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
          </svg>
          <span>退出登录</span>
        </button>
      </div>
    </aside>
  );
}

function Shell({ children }: { children: JSX.Element }) {
  return (
    <RequireAuth>
      <div className="app-shell">
        <Sidebar />
        <main className="app-main">{children}</main>
      </div>
    </RequireAuth>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/library" element={<Shell><Library /></Shell>} />
      <Route path="/drafts" element={<Shell><Drafts /></Shell>} />
      <Route path="/drafts/:id" element={<Shell><DraftDetail /></Shell>} />
      <Route path="/image-posts" element={<Shell><ImagePosts /></Shell>} />
      <Route path="/image-posts/:id" element={<Shell><ImagePostDetail /></Shell>} />
      <Route path="/image-assets" element={<Shell><ImageAssets /></Shell>} />
      <Route path="/accounts" element={<Shell><Accounts /></Shell>} />
      <Route path="/settings" element={<Shell><Settings /></Shell>} />
      <Route path="*" element={<Navigate to="/library" replace />} />
    </Routes>
  );
}
