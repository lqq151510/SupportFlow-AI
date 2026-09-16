import { Alert, Badge, Card } from "@/components/ui";

// 说明：当前 OpenAPI 契约（docs/contracts/openapi.json）尚未提供账号/成员管理端点，
// 依据 AGENTS.md §8「前端类型从 OpenAPI 生成，不得手写重复定义」，本页暂以只读信息呈现，
// 不虚构端点。后端补齐 members 管理接口后再升级为完整 CRUD。
const DEMO_ACCOUNTS = [
  { email: "customer@example.com", name: "演示客户", role: "USER", roleLabel: "客户" },
  { email: "agent@example.com", name: "演示坐席", role: "AGENT", roleLabel: "坐席" },
  { email: "admin@example.com", name: "演示管理员", role: "ADMIN", roleLabel: "管理员" },
];

export default function SettingsMembers() {
  return (
    <div className="page" style={{ maxWidth: 860 }}>
      <Alert kind="info">
        成员管理后端接口尚未在本阶段契约中提供（无 <span className="mono">/users</span> 系列端点），
        此页当前为只读信息展示；账号创建仍由管理员通过种子脚本完成。
      </Alert>

      <Card title="当前演示账号（只读）">
        <div className="hint" style={{ marginTop: 0, marginBottom: 12 }}>
          三个演示角色覆盖本阶段可见性差异，初始密码均为 <span className="mono">demo1234</span>（仅本地演示）。
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>邮箱</th>
              <th>显示名</th>
              <th>角色</th>
            </tr>
          </thead>
          <tbody>
            {DEMO_ACCOUNTS.map((u) => (
              <tr key={u.email}>
                <td className="mono">{u.email}</td>
                <td>{u.name}</td>
                <td>
                  <Badge
                    cls={u.role === "ADMIN" ? "badge-primary" : u.role === "AGENT" ? "badge-info" : "badge"}
                  >
                    {u.roleLabel}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
