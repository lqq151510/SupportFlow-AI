import { Link, useParams } from "react-router-dom";
import { UserTopbar } from "@/components/UserTopbar";
import { Alert, Badge, Card, Empty, Loading } from "@/components/ui";
import { useAsync } from "@/hooks/useAsync";
import { ticketApi } from "@/api/endpoints";
import { categoryLabel, formatDateTime, statusBadge } from "@/lib/format";

export default function TicketDetailUser() {
  const { id = "" } = useParams();
  const { data, loading, error } = useAsync(() => ticketApi.get(id), [id]);

  if (loading) return <UserTopbar title="工单详情"><Loading label="加载工单…" /></UserTopbar>;
  if (error)
    return (
      <UserTopbar title="工单详情">
        <Alert kind="danger">{error}</Alert>
        <Link to="/tickets" className="btn btn-sm">
          ← 返回列表
        </Link>
      </UserTopbar>
    );
  if (!data) return <UserTopbar title="工单详情"><Empty title="工单不存在" /></UserTopbar>;

  const sb = statusBadge(data.status);

  return (
    <UserTopbar title={data.subject}>
      <Link to="/tickets" className="btn btn-sm btn-ghost" style={{ marginBottom: 14 }}>
        ← 返回列表
      </Link>

      <div className="grid grid-2">
        <Card title="问题详情">
          <div className="row wrap" style={{ gap: 8, marginBottom: 10 }}>
            <span className="mono faint">{data.ticket_no}</span>
            <Badge cls={sb.cls as "badge"}>
              <span className="badge-dot" />
              {sb.label}
            </Badge>
            <span className="badge">{categoryLabel(data.category)}</span>
          </div>
          <div className="pre" style={{ whiteSpace: "pre-wrap" }}>
            {data.body_cleaned}
          </div>
          <div className="faint" style={{ fontSize: 12, marginTop: 10 }}>
            提交时间：{formatDateTime(data.created_at)}
          </div>
        </Card>

        <Card
          title="正式回复"
          actions={
            data.published_reply ? (
              <Badge cls="badge-success">已发布</Badge>
            ) : (
              <Badge cls="badge-warning">处理中</Badge>
            )
          }
        >
          {data.published_reply ? (
            <div className="pre" style={{ whiteSpace: "pre-wrap", lineHeight: 1.7 }}>
              {data.published_reply}
            </div>
          ) : (
            <Empty icon="⏳" title="暂未发布正式回复" hint="坐席正在审核草稿，请稍后刷新查看。" />
          )}
        </Card>
      </div>
    </UserTopbar>
  );
}
