import { useEffect, useRef, useState } from "react";
import { Alert, Badge, Card, Empty, Spinner } from "@/components/ui";
import { evaluationApi, type EvaluationImportOut, type EvaluationRunOut } from "@/api/endpoints";
import { formatDateTime, statusBadge } from "@/lib/format";

function Metrics({ metrics }: { metrics: Record<string, unknown> | null }) {
  if (!metrics) return <div className="faint">尚无指标</div>;
  const entries = Object.entries(metrics);
  return (
    <div className="grid grid-3" style={{ marginTop: 10 }}>
      {entries.map(([k, v]) => (
        <div key={k} className="card card-pad" style={{ padding: 14 }}>
          <div className="faint" style={{ fontSize: 12, textTransform: "capitalize" }}>
            {k.replace(/_/g, " ")}
          </div>
          <div style={{ fontWeight: 700, fontSize: 20, marginTop: 2 }}>
            {typeof v === "number" ? (Number.isInteger(v) ? v : v.toFixed(3)) : String(v)}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function Evaluations() {
  const [importInfo, setImportInfo] = useState<EvaluationImportOut | null>(null);
  const [mode, setMode] = useState("mock");
  const [limit, setLimit] = useState<number>(50);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [run, setRun] = useState<EvaluationRunOut | null>(null);
  const [polling, setPolling] = useState(false);
  const pollId = useRef<number | null>(null);

  const doImport = async () => {
    setBusy(true);
    setErr(null);
    try {
      setImportInfo(await evaluationApi.importCases());
    } catch (e) {
      setErr(e instanceof Error ? e.message : "导入失败");
    } finally {
      setBusy(false);
    }
  };

  const poll = (id: string) => {
    setPolling(true);
    const tick = async () => {
      try {
        const r = await evaluationApi.getRun(id);
        setRun(r);
        if (r.status === "COMPLETED" || r.status === "FAILED") {
          if (pollId.current) window.clearInterval(pollId.current);
          setPolling(false);
        }
      } catch {
        /* 容忍瞬时错误，下次轮询继续 */
      }
    };
    void tick();
    pollId.current = window.setInterval(tick, 1500);
  };

  useEffect(() => () => { if (pollId.current) window.clearInterval(pollId.current); }, []);

  const createRun = async () => {
    setBusy(true);
    setErr(null);
    try {
      const r = await evaluationApi.createRun({ mode, limit });
      setRun(r);
      poll(r.id);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "启动评测失败");
    } finally {
      setBusy(false);
    }
  };

  const sb = run ? statusBadge(run.status) : null;

  return (
    <div className="page" style={{ maxWidth: 980 }}>
      {err && <Alert kind="danger">{err}</Alert>}

      <div className="grid grid-2">
        <Card title="冻结评测集">
          <div className="hint" style={{ marginTop: 0, marginBottom: 10 }}>
            导入 50 条冻结用例（40 检索 + 10 安全/失败）与语料，幂等。
          </div>
          <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => void doImport()}>
            {busy ? <Spinner /> : "导入冻结用例"}
          </button>
          {importInfo && (
            <div className="muted" style={{ fontSize: 12.5, marginTop: 10 }}>
              新建 {importInfo.created} · 复用 {importInfo.reused} · 语料 {importInfo.corpus_docs} 篇
            </div>
          )}
        </Card>

        <Card title="执行评测">
          <div className="row wrap" style={{ gap: 8, marginBottom: 10 }}>
            <select className="select" style={{ width: "auto" }} value={mode} onChange={(e) => setMode(e.target.value)}>
              <option value="mock">Mock 模式</option>
              <option value="real">Real 模式</option>
            </select>
            <input
              className="input"
              style={{ width: 90 }}
              type="number"
              min={1}
              max={200}
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
            />
            <span className="faint" style={{ fontSize: 12 }}>条用例</span>
          </div>
          <button className="btn btn-primary btn-sm" disabled={busy || polling} onClick={() => void createRun()}>
            {polling ? <Spinner /> : "执行评测"}
          </button>
        </Card>
      </div>

      {run && (
        <Card title="评测结果" style={{ marginTop: 16 }}>
          <div className="row wrap" style={{ gap: 8, marginBottom: 6 }}>
            <span className="mono faint">{run.id}</span>
            {sb && (
              <Badge cls={sb.cls as "badge"}>
                <span className="badge-dot" />
                {sb.label}
              </Badge>
            )}
            <Badge cls="badge-info">{run.mode}</Badge>
            <span className="faint" style={{ fontSize: 12 }}>
              索引 {run.index_version}
            </span>
            <span className="faint" style={{ fontSize: 12 }}>
              {formatDateTime(run.started_at)} → {formatDateTime(run.finished_at)}
            </span>
            <a className="btn btn-sm btn-ghost" href={evaluationApi.reportUrl(run.id)} target="_blank" rel="noreferrer">
              下载报告 JSON
            </a>
          </div>
          {polling && <div className="muted" style={{ marginTop: 8 }}><Spinner /> 评测进行中…</div>}
          <Metrics metrics={run.metrics} />
        </Card>
      )}

      {!run && !polling && (
        <Empty icon="📊" title="尚未执行评测" hint="导入冻结用例后点击「执行评测」。" />
      )}
    </div>
  );
}
