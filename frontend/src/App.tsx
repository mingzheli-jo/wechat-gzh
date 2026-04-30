import type { JSX } from "react";
import { Link, Navigate, Route, Routes } from "react-router-dom";

import Accounts from "./pages/Accounts";
import Library from "./pages/Library";
import Login from "./pages/Login";

function isAuthed(): boolean {
  return Boolean(localStorage.getItem("token"));
}

function RequireAuth({ children }: { children: JSX.Element }) {
  return isAuthed() ? children : <Navigate to="/login" replace />;
}

function Nav() {
  return (
    <nav className="bg-slate-900 text-white px-6 py-3 flex gap-4">
      <Link to="/library">素材库</Link>
      <Link to="/accounts">公众号</Link>
      <button
        className="ml-auto"
        onClick={() => {
          localStorage.removeItem("token");
          window.location.href = "/login";
        }}
      >
        登出
      </button>
    </nav>
  );
}

function Shell({ children }: { children: JSX.Element }) {
  return (
    <RequireAuth>
      <>
        <Nav />
        {children}
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
        path="/accounts"
        element={
          <Shell>
            <Accounts />
          </Shell>
        }
      />
      <Route path="*" element={<Navigate to="/library" replace />} />
    </Routes>
  );
}
