import { useState } from "react";
import { Link } from "react-router-dom";
import { Alert, Badge, Card, Empty, Loading, Spinner } from "@/components/ui";
import { useAsync } from "@/hooks/useAsync";
import { approvalApi } from "@/api/endpoints";
import { genIdempotencyKey } from "@/api/client";
import { formatDateTime, statusBadge } from "@/lib/format";

const STATUSES = [
  { v: "PENDING", label: "待审批" },
  { v: "APPROVED", label: "已批准" },
  { v: "REJECTED", label: "已拒绝" },
  { v: "EXPIRED", label: "已过期" },
];

export default function Approvals() {
  const [status, setStatus] = useState("PENDING");
  const [busy, setBusy] = useState<string | null>(null);
  const { data, loading, error, reload } = useAsync(
    () => approvalApi.list({ status, limit: 50 }),
    [status],
  );

  const items = data?.items ?? [];

  const decide = async (id: string, approve: boolean) => {
    setBusy(id);
    try {
      await approvalApi.decide(id, approve, genIdempotencyKey());
      reload();
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="page">
      <div className="row row-between wrap" style={{ marginBottom: 14 }}>
        <div className="row" style={{ gap: 8 }}>
          {STATUSES.map((s) => (
            <button
              key={s.v}
              className={"btn btn-sm" + (status === s.v ? " btn-primary" : "")}
              onClick={() => setStatus(s.v)}
            >
              {s.label}
            </button>
          ))}
        </div>
        <button className="btn btn-ghost btn-sm" onClick={reload}>
          🔄 刷新
        </button>
      </div>

      {error && <Alert kind="danger">{error}</Alert>}
      {loading && <Loading label="加载审批…" />}
      {!loading && !error && items.length === 0 && (
        <Empty icon="✅" title="没有符合条件的审批" />
      )}

      {!loading &&
        !error &&
        items.map((a) => {
          const sb = statusBadge(a.status);
          return (
            <Card key={a.id} pad>
              <div className="row row-between wrap">
                <div className="row wrap" style={{ gap: 8 }}>
                  <Badge cls={sb.cls as "badge"}>{sb.label}</Badge>
                  <Badge cls="badge-warning">{a.action_type}</Badge>
                  <Link to={`/console/tickets/${a.ticket_id}`} className="mono faint">
                    工单 →
                  </Link>
                </div>
                <span className="faint" style={{ fontSize: 12 }}>
                  创建 {formatDateTime(a.created_at)}
                </span>
              </div>
              <div className="muted" style={{ margin: "10px 0", fontSize: 13.5 }}>
                {a.reason}
              </div>
              <div className="row wrap" style={{ gap: 14, fontSize: 12, color: "var(--text-faint)" }}>
                <span>工单版本 v{a.ticket_version}</span>
                <span>过期 {formatDateTime(a.expires_at)}</span>
                {a.decided_at && <span>决策 {formatDateTime(a.decided_at)}</span>}
              </div>
              {a.status === "PENDING" && (
                <div className="row" style={{ gap: 8, marginTop: 12 }}>
                  <button
                    className="btn btn-success btn-sm"
                    disabled={busy === a.id}
                    onClick={() => void decide(a.id, true)}
                  >
                    {busy === a.id ? <Spinner /> : "批准并执行"}
                  </button>
                  <button
                    className="btn btn-danger btn-sm"
                    disabled={busy === a.id}
                    onClick={() => void decide(a.id, false)}
                  >
                    拒绝
                  </button>
                </div>
              )}
            </Card>
          );
        })}
    </div>
  );
}
