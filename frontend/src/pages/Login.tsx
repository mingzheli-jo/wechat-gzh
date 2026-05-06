import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { Button } from "../components/ui";

export default function Login() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const form = new URLSearchParams({ username, password });
      const { data } = await api.post("/auth/login", form, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });
      localStorage.setItem("token", data.access_token);
      navigate("/library");
    } catch {
      setError("用户名或密码错误");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="login-shell"
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        minHeight: "100vh",
      }}
    >
      {/* LEFT — editorial brand panel */}
      <div
        style={{
          backgroundColor: "var(--color-ink)",
          color: "var(--color-white)",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "var(--space-12)",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Subtle grid texture */}
        <div
          aria-hidden="true"
          style={{
            position: "absolute",
            inset: 0,
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)",
            backgroundSize: "40px 40px",
            pointerEvents: "none",
          }}
        />

        {/* Top section: logo + headline */}
        <div style={{ position: "relative", zIndex: 1 }}>
          {/* Logo mark */}
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: "36px",
              height: "36px",
              borderRadius: "var(--radius-md)",
              border: "1px solid rgba(255,255,255,0.2)",
              fontSize: "15px",
              fontWeight: "var(--weight-semi)",
              fontFamily: "var(--font-sans)",
              marginBottom: "var(--space-12)",
            }}
          >
            微
          </div>

          {/* Eyebrow */}
          <p
            style={{
              margin: "0 0 var(--space-4) 0",
              fontSize: "10px",
              fontWeight: "var(--weight-semi)",
              fontFamily: "var(--font-sans)",
              textTransform: "uppercase",
              letterSpacing: "var(--tracking-wide)",
              color: "rgba(255,255,255,0.4)",
            }}
          >
            WeChat 公众号工作站
          </p>

          {/* Massive serif headline */}
          <h1
            className="text-display"
            style={{
              color: "var(--color-white)",
              margin: 0,
            }}
          >
            批量改写。
            <br />
            每一篇。
          </h1>
        </div>

        {/* Bottom manifesto */}
        <div style={{ position: "relative", zIndex: 1 }}>
          <div
            style={{
              borderTop: "1px solid rgba(255,255,255,0.1)",
              paddingTop: "var(--space-6)",
              display: "flex",
              flexDirection: "column",
              gap: "var(--space-4)",
            }}
          >
            {[
              { n: "01", text: "抓取 — 粘贴链接，自动获取原文" },
              { n: "02", text: "改写 — AI 重写标题与正文" },
              { n: "03", text: "推送 — 一键发到微信草稿箱" },
            ].map((item, i, arr) => (
              <div key={item.n}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "baseline",
                    gap: "var(--space-4)",
                  }}
                >
                  <span
                    className="mono"
                    style={{
                      color: "rgba(255,255,255,0.35)",
                      fontFamily: "var(--font-mono)",
                      fontSize: "var(--text-xs)",
                      flexShrink: 0,
                    }}
                  >
                    {item.n}
                  </span>
                  <span
                    style={{
                      fontSize: "var(--text-sm)",
                      color: "rgba(255,255,255,0.6)",
                    }}
                  >
                    {item.text}
                  </span>
                </div>
                {i < arr.length - 1 && (
                  <div
                    style={{
                      marginTop: "var(--space-4)",
                      height: "1px",
                      backgroundColor: "rgba(255,255,255,0.07)",
                    }}
                  />
                )}
              </div>
            ))}
          </div>
          <p
            style={{
              marginTop: "var(--space-8)",
              fontSize: "var(--text-xs)",
              color: "rgba(255,255,255,0.2)",
            }}
          >
            内部工具 · 仅限授权用户
          </p>
        </div>
      </div>

      {/* RIGHT — form panel */}
      <div
        style={{
          backgroundColor: "var(--color-surface)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "var(--space-12)",
        }}
      >
        <div
          className="animate-fade-in"
          style={{
            width: "100%",
            maxWidth: "360px",
          }}
        >
          <h2 className="text-section-title" style={{ marginBottom: "var(--space-2)" }}>
            登录
          </h2>
          <p className="text-page-subtitle" style={{ marginBottom: "var(--space-8)" }}>
            使用管理员账号继续
          </p>

          <form
            onSubmit={submit}
            style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}
          >
            <div>
              <label htmlFor="username" className="field-label">
                用户名
              </label>
              <input
                id="username"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                className="input-base"
                style={{ padding: "var(--space-3) var(--space-4)" }}
              />
            </div>

            <div>
              <label htmlFor="password" className="field-label">
                密码
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="input-base"
                style={{ padding: "var(--space-3) var(--space-4)" }}
              />
            </div>

            {error && (
              <div
                style={{
                  padding: "var(--space-3) var(--space-4)",
                  backgroundColor: "var(--color-failed)",
                  color: "var(--color-failed-fg)",
                  borderRadius: "var(--radius-md)",
                  fontSize: "var(--text-sm)",
                }}
              >
                {error}
              </div>
            )}

            <Button
              type="submit"
              variant="primary"
              size="lg"
              loading={loading}
              disabled={!username || !password}
              style={{ width: "100%", marginTop: "var(--space-2)" }}
            >
              登录
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
