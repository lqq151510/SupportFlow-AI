import { NavLink, useNavigate } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "@/auth/AuthContext";
import { roleLabel } from "@/lib/format";

export function UserTopbar({
  title,
  actions,
  children,
}: {
  title: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const { principal, logout } = useAuth();
  const navigate = useNavigate();

  const onLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="content" style={{ minHeight: "100vh" }}>
      <header
        className="topbar"
        style={{
          position: "static",
          display: "flex",
          alignItems: "center",
          gap: 18,
          padding: "0 20px",
        }}
      >
        <div className="row" style={{ gap: 4 }}>
          <span style={{ fontWeight: 700, fontSize: 15 }}>🪷 SupportFlow</span>
          <NavLink
            to="/tickets"
            className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}
            style={{ borderLeft: "none", padding: "8px 12px" }}
          >
            我的工单
          </NavLink>
          <NavLink
            to="/tickets/new"
            className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}
            style={{ borderLeft: "none", padding: "8px 12px" }}
          >
            提交工单
          </NavLink>
        </div>
        <div className="grow" />
        <div className="row" style={{ gap: 12 }}>
          {actions}
          {principal && (
            <div className="user-chip">
              <span className="avatar">{principal.display_name.slice(0, 1)}</span>
              <span style={{ fontWeight: 600 }}>{principal.display_name}</span>
              <span className="faint" style={{ fontSize: 12 }}>
                {roleLabel(principal.role)}
              </span>
              <button className="btn btn-sm btn-ghost" onClick={() => void onLogout()}>
                退出
              </button>
            </div>
          )}
        </div>
      </header>
      <main className="page">
        <div className="row row-between" style={{ marginBottom: 18 }}>
          <h1 style={{ fontSize: 20, margin: 0, fontWeight: 700 }}>{title}</h1>
        </div>
        {children}
      </main>
    </div>
  );
}
