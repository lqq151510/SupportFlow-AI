import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";
import { Alert, Field, Spinner } from "@/components/ui";

const DEMO = [
  { email: "customer@example.com", label: "客户" },
  { email: "agent@example.com", label: "坐席" },
  { email: "admin@example.com", label: "管理员" },
];
const DEMO_PASSWORD = "demo1234";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const from = (location.state as { from?: string } | null)?.from;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await login(email, password);
      navigate(from ?? (email.startsWith("customer") ? "/tickets" : "/console/queue"), { replace: true });
    } catch {
      setBusy(false);
    }
  };

  const fillDemo = (e: string) => {
    setEmail(e);
    setPassword(DEMO_PASSWORD);
  };

  return (
    <div className="auth-wrap">
      <div className="card auth-card">
        <div className="card-pad">
          <div style={{ textAlign: "center", marginBottom: 18 }}>
            <div style={{ fontSize: 30 }}>🪷</div>
            <h2 style={{ margin: "8px 0 2px", fontSize: 19 }}>SupportFlow Agent</h2>
            <div className="muted" style={{ fontSize: 13 }}>
              智能客服工单工作台
            </div>
          </div>

          {err && <Alert kind="danger">{err}</Alert>}

          <form onSubmit={submit}>
            <Field label="邮箱">
              <input
                className="input"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
              />
            </Field>
            <Field label="密码">
              <input
                className="input"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
              />
            </Field>
            <button className="btn btn-primary" style={{ width: "100%" }} disabled={busy}>
              {busy ? <Spinner /> : "登录"}
            </button>
          </form>

          <div className="h-divider" style={{ margin: "18px 0" }} />
          <div className="section-label">演示账号（密码 {DEMO_PASSWORD}）</div>
          <div className="row wrap" style={{ gap: 8 }}>
            {DEMO.map((d) => (
              <button
                key={d.email}
                type="button"
                className="btn btn-sm"
                onClick={() => fillDemo(d.email)}
                disabled={busy}
              >
                填入{d.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
