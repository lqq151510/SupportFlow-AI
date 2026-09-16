import { useRef, useState } from "react";
import { Alert, Badge, Card, Empty, Spinner } from "@/components/ui";
import { knowledgeApi, type ImportJobOut, type SearchPageOut } from "@/api/endpoints";
import { genIdempotencyKey } from "@/api/client";
import { formatDateTime } from "@/lib/format";

function JobResult({ job }: { job: ImportJobOut }) {
  const sb = job.duplicate ? "badge-info" : job.status === "COMPLETED" ? "badge-success" : "badge-warning";
  return (
    <div className="citation" style={{ background: "var(--surface-2)", marginTop: 10 }}>
      <div className="row row-between">
        <Badge cls={sb as "badge"}>{job.status}</Badge>
        <span className="faint" style={{ fontSize: 11 }}>{formatDateTime(job.created_at)}</span>
      </div>
      <div className="muted" style={{ fontSize: 12.5, marginTop: 6 }}>
        {job.source_name} · 进度 {Math.round(job.progress * 100)}% · 索引版本 {job.index_version || "—"}
        {job.duplicate && " · 内容重复已跳过"}
      </div>
    </div>
  );
}

export default function Knowledge() {
  const [docFile, setDocFile] = useState<File | null>(null);
  const [histFile, setHistFile] = useState<File | null>(null);
  const [busy, setBusy] = useState<"doc" | "hist" | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [docJob, setDocJob] = useState<ImportJobOut | null>(null);
  const [histJob, setHistJob] = useState<ImportJobOut | null>(null);

  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("mock");
  const [searching, setSearching] = useState(false);
  const [searchErr, setSearchErr] = useState<string | null>(null);
  const [results, setResults] = useState<SearchPageOut | null>(null);
  const docInput = useRef<HTMLInputElement>(null);
  const histInput = useRef<HTMLInputElement>(null);

  const uploadDoc = async () => {
    if (!docFile) return;
    setBusy("doc");
    setErr(null);
    try {
      const job = await knowledgeApi.importDocument(docFile, genIdempotencyKey());
      setDocJob(job);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "导入失败");
    } finally {
      setBusy(null);
      if (docInput.current) docInput.current.value = "";
      setDocFile(null);
    }
  };
  const uploadHist = async () => {
    if (!histFile) return;
    setBusy("hist");
    setErr(null);
    try {
      const job = await knowledgeApi.importHistory(histFile, genIdempotencyKey());
      setHistJob(job);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "导入失败");
    } finally {
      setBusy(null);
      if (histInput.current) histInput.current.value = "";
      setHistFile(null);
    }
  };
  const doSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    setSearchErr(null);
    try {
      const r = await knowledgeApi.search(query.trim(), 20);
      setResults(r);
    } catch (e) {
      setSearchErr(e instanceof Error ? e.message : "检索失败");
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="page" style={{ maxWidth: 980 }}>
      {err && <Alert kind="danger">{err}</Alert>}

      <div className="grid grid-2">
        <Card title="导入知识文档">
          <div className="hint" style={{ marginTop: 0, marginBottom: 10 }}>
            支持 FAQ CSV、Markdown、TXT、PDF、DOCX（扫描版 PDF 不支持 OCR）。
          </div>
          <input
            ref={docInput}
            type="file"
            className="input"
            onChange={(e) => setDocFile(e.target.files?.[0] ?? null)}
          />
          <button
            className="btn btn-primary btn-sm"
            style={{ marginTop: 10 }}
            disabled={!docFile || busy === "doc"}
            onClick={() => void uploadDoc()}
          >
            {busy === "doc" ? <Spinner /> : "上传并导入"}
          </button>
          {docJob && <JobResult job={docJob} />}
        </Card>

        <Card title="导入历史工单">
          <div className="hint" style={{ marginTop: 0, marginBottom: 10 }}>
            仅导入已关闭且具有正式回复的记录（CSV / JSONL）。
          </div>
          <input
            ref={histInput}
            type="file"
            className="input"
            onChange={(e) => setHistFile(e.target.files?.[0] ?? null)}
          />
          <button
            className="btn btn-primary btn-sm"
            style={{ marginTop: 10 }}
            disabled={!histFile || busy === "hist"}
            onClick={() => void uploadHist()}
          >
            {busy === "hist" ? <Spinner /> : "上传并导入"}
          </button>
          {histJob && <JobResult job={histJob} />}
        </Card>
      </div>

      <Card title="检索测试" style={{ marginTop: 16 }}>
        <div className="row wrap" style={{ gap: 8 }}>
          <input
            className="input grow"
            placeholder="输入检索问题，验证混合检索与引用…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && void doSearch()}
          />
          <select className="select" style={{ width: "auto" }} value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="mock">Mock</option>
            <option value="real">Real</option>
          </select>
          <button className="btn btn-primary" disabled={searching || !query.trim()} onClick={() => void doSearch()}>
            {searching ? <Spinner /> : "检索"}
          </button>
        </div>

        {searchErr && <Alert kind="danger">{searchErr}</Alert>}
        {results && results.items.length === 0 && (
          <Empty icon="🔍" title="无检索结果" hint="尝试更换问题，或先导入知识文档。" />
        )}
        {results && results.items.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <div className="section-label">
              召回 {results.items.length} 条 · 模式 {results.mode}
            </div>
            {results.items.map((it, i) => (
              <div className="citation" key={i}>
                <div className="row row-between">
                  <Badge cls="badge-info">{it.source_type}</Badge>
                  <span className="mono faint" style={{ fontSize: 11 }}>
                    {it.locator} · 融合分 {it.score.toFixed(4)}
                  </span>
                </div>
                <div className="quote pre">{it.quote_text}</div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
