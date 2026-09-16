import { useState } from "react";
import { Alert, Badge, Card, Loading, Spinner } from "@/components/ui";
import { useAsync } from "@/hooks/useAsync";
import {
  modelApi,
  type ConnectionTestOut,
  type ModelCapability,
  type ModelConfigOut,
} from "@/api/endpoints";
import { formatDateTime } from "@/lib/format";

export default function SettingsModels() {
  const { data, loading, error, reload } = useAsync(() => modelApi.list(), []);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [testResult, setTestResult] = useState<ConnectionTestOut | null>(null);

  const run = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(label);
    setMsg(null);
    setTestResult(null);
    try {
      await fn();
      reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "操作失败");
    } finally {
      setBusy(null);
    }
  };

  if (loading) return <Loading label="加载模型配置…" />;

  const items = data?.items ?? [];

  return (
    <div className="page" style={{ maxWidth: 980 }}>
      {error && <Alert kind="danger">{error}</Alert>}
      {msg && <Alert kind="danger">{msg}</Alert>}
      {testResult && (
        <Alert kind={testResult.ok ? "success" : "danger"}>
          {testResult.ok
            ? `连接成功：${testResult.model_name}（${testResult.latency_ms}ms）`
            : `连接失败：${testResult.error_code ?? ""} ${testResult.detail ?? ""}`}
        </Alert>
      )}

      <div className="row row-between" style={{ marginBottom: 14 }}>
        <span className="muted" style={{ fontSize: 13 }}>
          聊天与 Embedding 分别配置；API Key 仅以密文存储，查询不回显明文。
        </span>
        <button className="btn btn-primary btn-sm" onClick={() => setShowCreate((s) => !s)}>
          {showCreate ? "收起" : "＋ 新建配置"}
        </button>
      </div>

      {showCreate && (
        <CreateForm
          busy={busy === "create"}
          onCancel={() => setShowCreate(false)}
          onSubmit={async (body) => {
            await run("create", () => modelApi.create(body));
            setShowCreate(false);
          }}
        />
      )}

      {items.length === 0 && !showCreate && (
        <Alert kind="info">暂无模型配置，点击「新建配置」添加 OpenAI-compatible 端点。</Alert>
      )}

      {items.map((cfg) => (
        <Card key={cfg.id} pad style={{ marginBottom: 12 }}>
          <div className="row row-between wrap">
            <div className="row wrap" style={{ gap: 8 }}>
              <Badge cls={cfg.capability === "CHAT" ? "badge-primary" : "badge-info"}>
                {cfg.capability === "CHAT" ? "聊天" : "Embedding"}
              </Badge>
              <span style={{ fontWeight: 600 }}>{cfg.model_name}</span>
              <span className="mono faint" style={{ fontSize: 12 }}>{cfg.base_url}</span>
              {cfg.enabled && <Badge cls="badge-success">已启用</Badge>}
              {!cfg.api_key_configured && <Badge cls="badge-warning">未配置密钥</Badge>}
            </div>
            <div className="row" style={{ gap: 8 }}>
              <button
                className="btn btn-sm btn-ghost"
                disabled={busy === `test-${cfg.id}`}
                onClick={() => void run(`test-${cfg.id}`, async () => setTestResult(await modelApi.test(cfg.id)))}
              >
                {busy === `test-${cfg.id}` ? <Spinner /> : "连接测试"}
              </button>
              {!cfg.enabled && (
                <button
                  className="btn btn-sm btn-success"
                  disabled={busy === `enable-${cfg.id}`}
                  onClick={() => void run(`enable-${cfg.id}`, () => modelApi.enable(cfg.id))}
                >
                  {busy === `enable-${cfg.id}` ? <Spinner /> : "启用"}
                </button>
              )}
              <EditForm cfg={cfg} busy={busy === `edit-${cfg.id}`} onSave={(body) => run(`edit-${cfg.id}`, () => modelApi.update(cfg.id, body))} />
            </div>
          </div>
          <div className="faint" style={{ fontSize: 12, marginTop: 8 }}>
            更新 {formatDateTime(cfg.updated_at)}
            {cfg.embedding_dim ? ` · 维度 ${cfg.embedding_dim}` : ""} · 版本 v{cfg.version}
          </div>
        </Card>
      ))}
    </div>
  );
}

function CreateForm({
  busy,
  onCancel,
  onSubmit,
}: {
  busy: boolean;
  onCancel: () => void;
  onSubmit: (body: {
    capability: ModelCapability;
    protocol: "OPENAI_COMPATIBLE";
    base_url: string;
    model_name: string;
    api_key: string;
    embedding_dim?: number | null;
  }) => Promise<void>;
}) {
  const [capability, setCapability] = useState<ModelCapability>("CHAT");
  const [baseUrl, setBaseUrl] = useState("");
  const [modelName, setModelName] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [dim, setDim] = useState("");

  return (
    <Card title="新建模型配置" style={{ marginBottom: 14 }}>
      <div className="grid grid-2">
        <div className="field">
          <label>能力类型</label>
          <select className="select" value={capability} onChange={(e) => setCapability(e.target.value as ModelCapability)}>
            <option value="CHAT">聊天 CHAT</option>
            <option value="EMBEDDING">Embedding</option>
          </select>
        </div>
        <div className="field">
          <label>模型名称</label>
          <input className="input" value={modelName} onChange={(e) => setModelName(e.target.value)} placeholder="gpt-4o-mini" />
        </div>
        <div className="field">
          <label>Base URL</label>
          <input className="input" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://api.openai.com/v1" />
        </div>
        <div className="field">
          <label>API Key</label>
          <input className="input" type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="sk-..." />
        </div>
        {capability === "EMBEDDING" && (
          <div className="field">
            <label>Embedding 维度</label>
            <input className="input" type="number" value={dim} onChange={(e) => setDim(e.target.value)} placeholder="1536" />
          </div>
        )}
      </div>
      <div className="row" style={{ gap: 8 }}>
        <button
          className="btn btn-primary btn-sm"
          disabled={busy || !baseUrl || !modelName || !apiKey}
          onClick={() =>
            void onSubmit({
              capability,
              protocol: "OPENAI_COMPATIBLE",
              base_url: baseUrl,
              model_name: modelName,
              api_key: apiKey,
              embedding_dim: dim ? Number(dim) : null,
            })
          }
        >
          {busy ? <Spinner /> : "创建"}
        </button>
        <button className="btn btn-sm" onClick={onCancel}>
          取消
        </button>
      </div>
    </Card>
  );
}

function EditForm({
  cfg,
  busy,
  onSave,
}: {
  cfg: ModelConfigOut;
  busy: boolean;
  onSave: (body: {
    base_url?: string | null;
    model_name?: string | null;
    api_key?: string | null;
    embedding_dim?: number | null;
  }) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [baseUrl, setBaseUrl] = useState("");
  const [modelName, setModelName] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [dim, setDim] = useState("");

  if (!open) {
    return (
      <button className="btn btn-sm btn-ghost" disabled={busy} onClick={() => setOpen(true)}>
        编辑
      </button>
    );
  }
  return (
    <span className="row" style={{ gap: 6 }}>
      <input className="input" style={{ width: 160 }} placeholder="Base URL" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
      <input className="input" style={{ width: 130 }} placeholder="模型名" value={modelName} onChange={(e) => setModelName(e.target.value)} />
      <input className="input" style={{ width: 130 }} type="password" placeholder="新 Key(可选)" value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
      {cfg.capability === "EMBEDDING" && (
        <input className="input" style={{ width: 80 }} type="number" placeholder="维度" value={dim} onChange={(e) => setDim(e.target.value)} />
      )}
      <button
        className="btn btn-sm btn-primary"
        disabled={busy}
        onClick={() =>
          void onSave({
            base_url: baseUrl || null,
            model_name: modelName || null,
            api_key: apiKey || null,
            embedding_dim: dim ? Number(dim) : null,
          }).then(() => setOpen(false))
        }
      >
        {busy ? <Spinner /> : "保存"}
      </button>
      <button className="btn btn-sm" onClick={() => setOpen(false)}>
        取消
      </button>
    </span>
  );
}
