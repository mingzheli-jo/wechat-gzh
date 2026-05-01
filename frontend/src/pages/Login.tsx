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
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        minHeight: "100vh",
        fontFamily: "var(--font-sans)",
      }}
    >
      {/* Left panel — brand / editorial side */}
      <div
        style={{
          backgroundColor: "var(--color-ink)",
          color: "var(--color-accent-fg)",
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

        {/* Logo */}
        <div style={{ position: "relative", zIndex: 1 }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: "40px",
              height: "40px",
              borderRadius: "var(--radius-md)",
              border: "1px solid rgba(255,255,255,0.15)",
              fontSize: "18px",
              fontWeight: "var(--weight-semi)",
              letterSpacing: "-0.5px",
              marginBottom: "var(--space-12)",
            }}
          >
            微
          </div>

          <h1
            style={{
              fontSize: "clamp(2rem, 3vw, 3rem)",
              fontWeight: "var(--weight-semi)",
              lineHeight: "var(--leading-tight)",
              letterSpacing: "-0.03em",
              margin: 0,
            }}
          >
            微信公众号
            <br />
            批量改写工具
          </h1>
          <p
            style={{
              marginTop: "var(--space-5)",
              fontSize: "var(--text-base)",
              color: "rgba(255,255,255,0.5)",
              lineHeight: "var(--leading-normal)",
              maxWidth: "28ch",
            }}
          >
            素材抓取、AI 改写、审核报告、一键推送——单人工作站，完整工作流。
          </p>
        </div>

        {/* Bottom footnote */}
        <p
          style={{
            position: "relative",
            zIndex: 1,
            fontSize: "var(--text-xs)",
            color: "rgba(255,255,255,0.25)",
            margin: 0,
          }}
        >
          内部工具 · 仅限授权用户
        </p>
      </div>

      {/* Right panel — form */}
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
          style={{
            width: "100%",
            maxWidth: "360px",
            animation: "fade-in 0.3s var(--ease-out) both",
          }}
        >
          <h2
            style={{
              fontSize: "var(--text-xl)",
              fontWeight: "var(--weight-semi)",
              color: "var(--color-ink)",
              letterSpacing: "-0.02em",
              margin: "0 0 var(--space-2) 0",
            }}
          >
            登录
          </h2>
          <p
            style={{
              fontSize: "var(--text-sm)",
              color: "var(--color-ink-3)",
              margin: "0 0 var(--space-8) 0",
            }}
          >
            使用管理员账号继续
          </p>

          <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
              <label
                htmlFor="username"
                style={{
                  fontSize: "var(--text-sm)",
                  fontWeight: "var(--weight-medium)",
                  color: "var(--color-ink-2)",
                }}
              >
                用户名
              </label>
              <input
                id="username"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                style={{
                  width: "100%",
                  padding: "var(--space-3) var(--space-4)",
                  fontSize: "var(--text-base)",
                  color: "var(--color-ink)",
                  backgroundColor: "var(--color-white)",
                  border: "1px solid var(--color-surface-3)",
                  borderRadius: "var(--radius-md)",
                  outline: "none",
                  transition: "border-color var(--dur-fast)",
                  boxSizing: "border-box",
                }}
                onFocus={(e) => { e.currentTarget.style.borderColor = "var(--color-ink)"; }}
                onBlur={(e) => { e.currentTarget.style.borderColor = "var(--color-surface-3)"; }}
              />
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
              <label
                htmlFor="password"
                style={{
                  fontSize: "var(--text-sm)",
                  fontWeight: "var(--weight-medium)",
                  color: "var(--color-ink-2)",
                }}
              >
                密码
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                style={{
                  width: "100%",
                  padding: "var(--space-3) var(--space-4)",
                  fontSize: "var(--text-base)",
                  color: "var(--color-ink)",
                  backgroundColor: "var(--color-white)",
                  border: "1px solid var(--color-surface-3)",
                  borderRadius: "var(--radius-md)",
                  outline: "none",
                  transition: "border-color var(--dur-fast)",
                  boxSizing: "border-box",
                }}
                onFocus={(e) => { e.currentTarget.style.borderColor = "var(--color-ink)"; }}
                onBlur={(e) => { e.currentTarget.style.borderColor = "var(--color-surface-3)"; }}
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
