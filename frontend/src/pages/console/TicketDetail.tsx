import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Alert, Badge, Card, Empty, Loading, Spinner } from "@/components/ui";
import { useAsync } from "@/hooks/useAsync";
import { useRunEvents } from "@/hooks/useRunEvents";
import { approvalApi, ticketApi, type DraftDetailOut } from "@/api/endpoints";
import { genIdempotencyKey } from "@/api/client";
import { categoryLabel, formatDateTime, relativeTime, statusBadge } from "@/lib/format";
import { describeEvent } from "@/lib/events";

export default function TicketDetailConsole() {
  const { id = "" } = useParams();
  const [modelMode, setModelMode] = useState<string>("mock");

  const ticketQ = useAsync(() => ticketApi.get(id), [id]);
  const draftsQ = useAsync(() => ticketApi.listDrafts(id), [id]);
  const runsQ = useAsync(() => ticketApi.listRuns(id), [id]);
  const approvalsQ = useAsync(() => approvalApi.list({ status: "PENDING" }), [id]);

  const [draftBusy, setDraftBusy] = useState(false);
  const [runBusy, setRunBusy] = useState(false);
  const [approveBusy, setApproveBusy] = useState<string | null>(null);

  const reloadAll = () => {
    ticketQ.reload();
    draftsQ.reload();
    runsQ.reload();
    approvalsQ.reload();
  };

  if (ticketQ.loading) return <Loading label="加载工单…" />;
  if (ticketQ.error)
    return (
      <div className="page">
        <Alert kind="danger">{ticketQ.error}</Alert>
        <Link to="/console/queue" className="btn btn-sm">
          ← 返回队列
        </Link>
      </div>
    );
  const ticket = ticketQ.data!;

  const drafts: DraftDetailOut[] = (draftsQ.data ?? []).slice().sort((a, b) => a.version - b.version);
  const activeDraft = drafts.find((d) => d.status === "ACTIVE");
  const latestRun = (runsQ.data?.items ?? [])
    .slice()
    .sort((a, b) => (a.created_at < b.created_at ? 1 : -1))[0];
  const { events, connected, terminal } = useRunEvents(latestRun?.id ?? null, latestRun != null);

  const ticketApprovals = (approvalsQ.data?.items ?? []).filter((a) => a.ticket_id === id);
  const sb = statusBadge(ticket.status);

  // ---- handlers ----
  const saveDraft = async (content: string) => {
    if (!activeDraft) return;
    setDraftBusy(true);
    try {
      await ticketApi.editDraft(id, activeDraft.id, content, genIdempotencyKey());
      draftsQ.reload();
      ticketQ.reload();
    } finally {
      setDraftBusy(false);
    }
  };
  const publishDraft = async () => {
    if (!activeDraft) return;
    setDraftBusy(true);
    try {
      await ticketApi.publishDraft(id, activeDraft.id, genIdempotencyKey());
      reloadAll();
    } finally {
      setDraftBusy(false);
    }
  };
  const startRun = async () => {
    setRunBusy(true);
    try {
      await ticketApi.startRun(id, modelMode, genIdempotencyKey());
      runsQ.reload();
    } finally {
      setRunBusy(false);
    }
  };
  const decide = async (requestId: string, approve: boolean) => {
    setApproveBusy(requestId);
    try {
      await approvalApi.decide(requestId, approve, genIdempotencyKey());
      reloadAll();
    } finally {
      setApproveBusy(null);
    }
  };

  return (
    <div className="page">
      <div className="row row-between wrap" style={{ marginBottom: 14 }}>
        <Link to="/console/queue" className="btn btn-sm btn-ghost">
          ← 返回队列
        </Link>
        <div className="row" style={{ gap: 8 }}>
          <select
            className="select"
            style={{ width: "auto" }}
            value={modelMode}
            onChange={(e) => setModelMode(e.target.value)}
          >
            <option value="mock">Mock 运行</option>
            <option value="real">Real 运行</option>
          </select>
          <button className="btn btn-primary btn-sm" disabled={runBusy} onClick={() => void startRun()}>
            {runBusy ? <Spinner /> : "↻ 重新发起运行"}
          </button>
        </div>
      </div>

      {(draftsQ.error || runsQ.error) && (
        <Alert kind="danger">{draftsQ.error || runsQ.error}</Alert>
      )}

      <div className="detail-cols">
        {/* 左列：工单 + 运行实时进度 */}
        <div className="stack">
          <Card title="工单信息">
            <div className="row wrap" style={{ gap: 8, marginBottom: 10 }}>
              <span className="mono faint">{ticket.ticket_no}</span>
              <Badge cls={sb.cls as "badge"}>
                <span className="badge-dot" />
                {sb.label}
              </Badge>
              <span className="badge">{categoryLabel(ticket.category)}</span>
            </div>
            <div className="pre" style={{ whiteSpace: "pre-wrap" }}>
              {ticket.body_cleaned}
            </div>
            <div className="faint" style={{ fontSize: 12, marginTop: 10 }}>
              提交时间：{formatDateTime(ticket.created_at)}
            </div>
          </Card>

          <Card
            title="运行实时进度"
            actions={
              latestRun ? (
                <div className="row" style={{ gap: 6 }}>
                  <Badge cls={statusBadge(latestRun.status).cls as "badge"}>
                    {statusBadge(latestRun.status).label}
                  </Badge>
                  {connected ? (
                    <span className="badge badge-success">● 实时</span>
                  ) : terminal ? (
                    <span className="badge">已结束</span>
                  ) : (
                    <span className="badge">连接中</span>
                  )}
                  <Link to={`/console/runs/${latestRun.id}`} className="btn btn-sm btn-ghost">
                    详情
                  </Link>
                </div>
              ) : (
                <span className="faint" style={{ fontSize: 12 }}>
                  暂无运行
                </span>
              )
            }
          >
            {!latestRun && <Empty icon="🚀" title="尚未运行" hint="点击右上角「重新发起运行」。" />}
            {latestRun && events.length === 0 && (
              <div className="muted">
                {connected ? "等待事件推流…" : "连接中…"}
              </div>
            )}
            {latestRun && events.length > 0 && (
              <div>
                {events.map((ev) => (
                  <div className="step" key={ev.id}>
                    <span className="step-dot run">↻</span>
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

        {/* 右列：草稿编辑 + 引用 + 审批 */}
        <div className="stack">
          <DraftPanel
            drafts={drafts}
            activeDraft={activeDraft}
            busy={draftBusy}
            onSave={saveDraft}
            onPublish={publishDraft}
          />

          <Card title="待审批操作" actions={<Badge cls="badge-warning">{ticketApprovals.length}</Badge>}>
            {ticketApprovals.length === 0 && (
              <Empty icon="✅" title="无待审批操作" />
            )}
            {ticketApprovals.map((a) => (
              <div
                key={a.id}
                className="citation"
                style={{ background: "var(--surface-2)" }}
              >
                <div className="row row-between">
                  <Badge cls="badge-warning">{a.action_type}</Badge>
                  <span className="faint" style={{ fontSize: 11 }}>
                    过期 {formatDateTime(a.expires_at)}
                  </span>
                </div>
                <div className="muted" style={{ fontSize: 12.5, margin: "6px 0" }}>
                  {a.reason}
                </div>
                <div className="row" style={{ gap: 8 }}>
                  <button
                    className="btn btn-success btn-sm"
                    disabled={approveBusy === a.id}
                    onClick={() => void decide(a.id, true)}
                  >
                    {approveBusy === a.id ? <Spinner /> : "批准并执行"}
                  </button>
                  <button
                    className="btn btn-danger btn-sm"
                    disabled={approveBusy === a.id}
                    onClick={() => void decide(a.id, false)}
                  >
                    拒绝
                  </button>
                  <Link to="/console/approvals" className="btn btn-sm btn-ghost">
                    去审批中心
                  </Link>
                </div>
              </div>
            ))}
          </Card>
        </div>
      </div>
    </div>
  );
}

function DraftPanel({
  drafts,
  activeDraft,
  busy,
  onSave,
  onPublish,
}: {
  drafts: DraftDetailOut[];
  activeDraft: DraftDetailOut | undefined;
  busy: boolean;
  onSave: (content: string) => Promise<void>;
  onPublish: () => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState("");

  if (drafts.length === 0 || !activeDraft) {
    return (
      <Card title="草稿与回复">
        <Empty icon="📝" title="暂无草稿" hint="运行结束后此处会出现待审核回复。" />
      </Card>
    );
  }

  const citations = (activeDraft.citations ?? []) as Array<Record<string, unknown>>;

  return (
    <Card
      title={`草稿 v${activeDraft.version}（${activeDraft.author === "AGENT" ? "模型生成" : "人工编辑"}）`}
      actions={
        activeDraft.published_at ? (
          <Badge cls="badge-success">已发布</Badge>
        ) : (
          <Badge cls="badge-primary">当前版本</Badge>
        )
      }
    >
      {!editing ? (
        <div>
          <div className="pre" style={{ whiteSpace: "pre-wrap", lineHeight: 1.7 }}>
            {activeDraft.content}
          </div>
          {activeDraft.published_at && (
            <div className="faint" style={{ fontSize: 12, marginTop: 8 }}>
              发布于 {formatDateTime(activeDraft.published_at)}
            </div>
          )}
          {!activeDraft.published_at && (
            <div className="row" style={{ gap: 8, marginTop: 12 }}>
              <button className="btn btn-sm" disabled={busy} onClick={() => { setText(activeDraft.content); setEditing(true); }}>
                ✎ 编辑
              </button>
              <button className="btn btn-success btn-sm" disabled={busy} onClick={() => void onPublish()}>
                {busy ? <Spinner /> : "✓ 发布正式回复"}
              </button>
            </div>
          )}
        </div>
      ) : (
        <div>
          <textarea
            className="textarea"
            value={text}
            onChange={(e) => setText(e.target.value)}
            style={{ minHeight: 160 }}
          />
          <div className="row" style={{ gap: 8, marginTop: 10 }}>
            <button
              className="btn btn-primary btn-sm"
              disabled={busy || text.trim().length === 0}
              onClick={() => void onSave(text).then(() => setEditing(false))}
            >
              {busy ? <Spinner /> : "保存编辑（新版本）"}
            </button>
            <button className="btn btn-sm" disabled={busy} onClick={() => setEditing(false)}>
              取消
            </button>
          </div>
          <div className="hint">保存将派生新版本（作者=人工），旧版本自动归档。</div>
        </div>
      )}

      {/* 引用证据 */}
      <div className="h-divider" style={{ margin: "14px 0" }} />
      <div className="section-label">来源证据（{citations.length}）</div>
      {citations.length === 0 && <div className="faint" style={{ fontSize: 12.5 }}>无引用</div>}
      {citations.map((c, i) => (
        <div className="citation" key={i}>
          <div className="row row-between">
            <span className="badge badge-info">{String(c["source_type"] ?? "?")}</span>
            <span className="mono faint" style={{ fontSize: 11 }}>
              {String(c["locator"] ?? "")}
            </span>
          </div>
          <div className="quote pre">{String(c["quote_text"] ?? "")}</div>
        </div>
      ))}

      {/* 版本历史 */}
      {drafts.length > 1 && (
        <>
          <div className="h-divider" style={{ margin: "14px 0" }} />
          <div className="section-label">版本历史</div>
          <div className="stack" style={{ gap: 6 }}>
            {drafts
              .slice()
              .reverse()
              .map((d) => (
                <div key={d.id} className="row row-between" style={{ fontSize: 12.5 }}>
                  <span>
                    v{d.version} · {d.author === "AGENT" ? "模型" : "人工"}
                  </span>
                  <Badge cls={statusBadge(d.status).cls as "badge"}>{statusBadge(d.status).label}</Badge>
                </div>
              ))}
          </div>
        </>
      )}
    </Card>
  );
}
