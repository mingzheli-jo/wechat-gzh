import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../api/client";

export default function Login() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const form = new URLSearchParams({ username, password });
      const { data } = await api.post("/auth/login", form, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });
      localStorage.setItem("token", data.access_token);
      navigate("/accounts");
    } catch {
      setError("用户名或密码错误");
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <form
        onSubmit={submit}
        className="w-80 space-y-4 bg-white p-6 rounded-lg shadow"
      >
        <h1 className="text-xl font-semibold">登录</h1>
        <input
          className="w-full border rounded px-3 py-2"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="用户名"
        />
        <input
          type="password"
          className="w-full border rounded px-3 py-2"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="密码"
        />
        {error && <div className="text-red-500 text-sm">{error}</div>}
        <button className="w-full bg-slate-900 text-white py-2 rounded">
          登录
        </button>
      </form>
    </div>
  );
}
