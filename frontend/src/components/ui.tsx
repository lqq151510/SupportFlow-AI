import type { ReactNode } from "react";

export function Spinner({ large = false }: { large?: boolean }) {
  return <span className={large ? "spinner spinner-lg" : "spinner"} aria-label="加载中" />;
}

export function CenterFill({ children }: { children: ReactNode }) {
  return <div className="center-fill">{children}</div>;
}

export function Loading({ label = "加载中…" }: { label?: string }) {
  return (
    <CenterFill>
      <Spinner large />
      <div className="muted">{label}</div>
    </CenterFill>
  );
}

export function Empty({ icon = "📭", title, hint }: { icon?: string; title: string; hint?: string }) {
  return (
    <div className="empty">
      <span className="ico">{icon}</span>
      <div style={{ fontWeight: 600, color: "var(--text-muted)" }}>{title}</div>
      {hint && <div className="faint" style={{ marginTop: 4 }}>{hint}</div>}
    </div>
  );
}

export function Alert({ kind = "info", children }: { kind?: "info" | "danger" | "success"; children: ReactNode }) {
  const cls = kind === "danger" ? "alert-danger" : kind === "success" ? "alert-success" : "alert-info";
  return (
    <div className={`alert ${cls}`}>
      <span>{kind === "danger" ? "⚠️" : kind === "success" ? "✅" : "ℹ️"}</span>
      <div>{children}</div>
    </div>
  );
}

export function Badge({
  children,
  cls = "badge",
}: {
  children: ReactNode;
  cls?: "badge" | "badge-primary" | "badge-success" | "badge-warning" | "badge-danger" | "badge-info";
}) {
  return <span className={cls}>{children}</span>;
}

export function Card({
  title,
  actions,
  children,
  pad = true,
  style,
}: {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  pad?: boolean;
  style?: React.CSSProperties;
}) {
  return (
    <div className="card" style={style}>
      {title && (
        <div className="card-header">
          <div className="card-title">{title}</div>
          {actions}
        </div>
      )}
      <div className={pad ? "card-pad" : ""}>{children}</div>
    </div>
  );
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="field">
      <label>{label}</label>
      {children}
      {hint && <div className="hint">{hint}</div>}
    </div>
  );
}

// 带加载/错误/成功态的提交按钮组件。onSubmit 必须返回 Promise。
export function SubmitButton({
  onClick,
  children,
  variant = "btn-primary",
  disabled,
  idleLabel,
}: {
  onClick: () => Promise<void>;
  children: ReactNode;
  variant?: string;
  disabled?: boolean;
  idleLabel?: string;
}) {
  return (
    <button className={`btn ${variant}`} disabled={disabled} onClick={() => void onClick()}>
      {children}
      {idleLabel ? null : null}
    </button>
  );
}
