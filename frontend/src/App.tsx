import type { JSX } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import Accounts from "./pages/Accounts";
import Login from "./pages/Login";

function isAuthed(): boolean {
  return Boolean(localStorage.getItem("token"));
}

function RequireAuth({ children }: { children: JSX.Element }) {
  return isAuthed() ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/accounts"
        element={
          <RequireAuth>
            <Accounts />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/accounts" replace />} />
    </Routes>
  );
}
