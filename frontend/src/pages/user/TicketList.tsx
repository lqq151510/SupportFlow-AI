import { useState } from "react";
import { Link } from "react-router-dom";
import { UserTopbar } from "@/components/UserTopbar";
import { Alert, Badge, Empty, Loading } from "@/components/ui";
import { useAuth } from "@/auth/AuthContext";
import { useAsync } from "@/hooks/useAsync";
import { ticketApi, type TicketStatus } from "@/api/endpoints";
import { categoryLabel, formatDateTime, statusBadge } from "@/lib/format";

export default function TicketList() {
  const { isStaff } = useAuth();
  const [status, setStatus] = useState<TicketStatus | "">("");

  const { data, loading, error, reload } = useAsync(
    () => ticketApi.list({ status: status || null, limit: 50 }),
    [status],
  );

  const items = data?.items ?? [];

  return (
    <UserTopbar title={isStaff ? "全部工单" : "我的工单"}>
      <div className="row row-between wrap" style={{ marginBottom: 14 }}>
        <div className="row" style={{ gap: 8 }}>
          <select
            className="select"
            style={{ width: "auto" }}
            value={status}
            onChange={(e) => setStatus(e.target.value as TicketStatus | "")}
          >
            <option value="">全部状态</option>
            <option value="OPEN">处理中</option>
            <option value="CLOSED">已关闭</option>
          </select>
          <button className="btn btn-ghost btn-sm" onClick={reload}>
            🔄 刷新
          </button>
        </div>
        <Link to="/tickets/new" className="btn btn-primary">
          ＋ 提交工单
        </Link>
      </div>

      {error && <Alert kind="danger">{error}</Alert>}
      {loading && <Loading label="加载工单列表…" />}
      {!loading && !error && items.length === 0 && (
        <Empty icon="🎫" title="暂无工单" hint="点击右上角「提交工单」创建第一张工单。" />
      )}

      {!loading && !error && items.length > 0 && (
        <div className="card">
          <table className="table">
            <thead>
              <tr>
                <th>工单号</th>
                <th>主题</th>
                <th>分类</th>
                <th>状态</th>
                <th>提交时间</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.map((t) => {
                const sb = statusBadge(t.status);
                return (
                  <tr key={t.id}>
                    <td className="mono nowrap">{t.ticket_no}</td>
                    <td>
                      <Link to={`/tickets/${t.id}`}>{t.subject}</Link>
                    </td>
                    <td className="muted">{categoryLabel(t.category)}</td>
                    <td>
                      <Badge cls={sb.cls as "badge"}>
                        <span className="badge-dot" />
                        {sb.label}
                      </Badge>
                    </td>
                    <td className="muted nowrap">{formatDateTime(t.created_at)}</td>
                    <td className="nowrap">
                      <Link to={`/tickets/${t.id}`} className="btn btn-sm btn-ghost">
                        查看
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </UserTopbar>
  );
}
