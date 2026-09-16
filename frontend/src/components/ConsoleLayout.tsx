import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";
import { roleLabel } from "@/lib/format";
import { Spinner } from "./ui";

const NAV = [
  {
    group: "工作台",
    items: [
      { to: "/console/queue", label: "工单队列", icon: "🗂️", staff: true },
      { to: "/console/approvals", label: "审批中心", icon: "✅", staff: true },
    ],
  },
  {
    group: "知识库",
    items: [
      { to: "/console/knowledge", label: "知识导入", icon: "📚", staff: true },
      { to: "/console/evaluations", label: "评测视图", icon: "📊", staff: true },
    ],
  },
  {
    group: "系统",
    items: [
      { to: "/console/settings/models", label: "模型设置", icon: "⚙️", staff: true },
      { to: "/console/settings/members", label: "成员管理", icon: "👥", admin: true },
    ],
  },
];

export function ConsoleLayout() {
  const { principal, isStaff, isAdmin, logout } = useAuth();
  const navigate = useNavigate();

  const onLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="logo">🪷</span>
          <span>SupportFlow</span>
        </div>
        {NAV.map((g) => (
          <div key={g.group}>
            <div className="nav-group-label">{g.group}</div>
            {g.items
              .filter((it) => (it.admin ? isAdmin : isStaff))
              .map((it) => (
                <NavLink
                  key={it.to}
                  to={it.to}
                  className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}
                >
                  <span className="ico">{it.icon}</span>
                  {it.label}
                </NavLink>
              ))}
          </div>
        ))}
        <div className="sidebar-footer">
          <a href="/tickets">切换到客户视图 →</a>
        </div>
      </aside>

      <div className="content">
        <header className="topbar">
          <div className="crumbs">坐席工作台</div>
          {principal && (
            <div className="user-chip">
              <span className="muted" style={{ fontSize: 12 }}>
                {roleLabel(principal.role)}
              </span>
              <span className="avatar">{principal.display_name.slice(0, 1)}</span>
              <span style={{ fontWeight: 600 }}>{principal.display_name}</span>
              <button className="btn btn-sm btn-ghost" onClick={() => void onLogout()}>
                退出
              </button>
            </div>
          )}
        </header>
        <main style={{ flex: 1 }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export function TopbarLoading() {
  return (
    <div className="center-fill">
      <Spinner large />
    </div>
  );
}
