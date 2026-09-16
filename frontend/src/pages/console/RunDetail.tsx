import { Link, useParams } from "react-router-dom";
import { Alert, Badge, Card, Empty, Loading } from "@/components/ui";
import { useAsync } from "@/hooks/useAsync";
import { useRunEvents } from "@/hooks/useRunEvents";
import { runApi } from "@/api/endpoints";
import { describeEvent } from "@/lib/events";
import { formatDateTime, relativeTime, statusBadge } from "@/lib/format";

export default function RunDetail() {
  const { id = "" } = useParams();
  const { data, loading, error } = useAsync(() => runApi.get(id), [id]);
  const { events, connected, terminal } = useRunEvents(id, id != null);

  if (loading) return <Loading label="加载运行…" />;
  if (error)
    return (
      <div className="page">
        <Alert kind="danger">{error}</Alert>
        <Link to="/console/queue" className="btn btn-sm">
          ← 返回队列
        </Link>
      </div>
    );
  const run = data!;
  const sb = statusBadge(run.status);

  return (
    <div className="page">
      <Link to="/console/queue" className="btn btn-sm btn-ghost" style={{ marginBottom: 14 }}>
        ← 返回队列
      </Link>

      <Card title="运行概览">
        <div className="row wrap" style={{ gap: 8, marginBottom: 10 }}>
          <span className="mono faint">{run.id}</span>
          <Badge cls={sb.cls as "badge"}>
            <span className="badge-dot" />
            {sb.label}
          </Badge>
          <Badge cls="badge-info">{run.model_mode}</Badge>
          {run.chat_model_name && <Badge cls="badge">{run.chat_model_name}</Badge>}
        </div>
        <div className="grid grid-3" style={{ fontSize: 13 }}>
          <div>
            <div className="faint">步骤数</div>
            <div style={{ fontWeight: 600 }}>{run.step_count}</div>
          </div>
          <div>
            <div className="faint">工具调用</div>
            <div style={{ fontWeight: 600 }}>{run.tool_call_count}</div>
          </div>
          <div>
            <div className="faint">错误码</div>
            <div style={{ fontWeight: 600 }}>{run.error_code || "—"}</div>
          </div>
          <div>
            <div className="faint">开始</div>
            <div>{formatDateTime(run.started_at)}</div>
          </div>
          <div>
            <div className="faint">结束</div>
            <div>{formatDateTime(run.finished_at)}</div>
          </div>
          <div>
            <div className="faint">重试自</div>
            <div className="mono" style={{ fontSize: 12 }}>
              {run.retry_of_run_id ? run.retry_of_run_id.slice(0, 8) : "—"}
            </div>
          </div>
        </div>
        <div className="row" style={{ gap: 8, marginTop: 12 }}>
          <Link to={`/console/tickets/${run.ticket_id}`} className="btn btn-sm">
            查看工单
          </Link>
          <span className="faint" style={{ fontSize: 12 }}>
            {connected ? (
              <span className="badge badge-success">● 实时推流中</span>
            ) : terminal ? (
              <span className="badge">流已结束</span>
            ) : (
              <span className="badge">连接中…</span>
            )}
          </span>
        </div>
      </Card>

      <Card title="事件时间线" style={{ marginTop: 16 }}>
        {events.length === 0 && <Empty icon="⏱️" title="暂无事件" hint="等待运行产生事件…" />}
        {events.length > 0 && (
          <div>
            {events.map((ev) => (
              <div className="step" key={ev.id}>
                <span className={"step-dot " + (ev.type.includes("completed") || ev.type.includes("created") ? "ok" : "run")}>
                  {ev.type.includes("completed") || ev.type.includes("created") ? "✓" : "↻"}
                </span>
                <div className="grow">
                  <div className="row row-between">
                    <Badge cls="badge-info">{ev.type}</Badge>
                    <span className="faint" style={{ fontSize: 11 }}>
                      {relativeTime(ev.created_at)}
                    </span>
                  </div>
                  <div className="muted" style={{ fontSize: 12.5, marginTop: 3 }}>
                    {describeEvent(ev)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
