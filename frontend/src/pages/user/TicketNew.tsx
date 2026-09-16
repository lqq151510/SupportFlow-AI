import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { UserTopbar } from "@/components/UserTopbar";
import { Alert, Field, Spinner } from "@/components/ui";
import { useAuth } from "@/auth/AuthContext";
import { ticketApi } from "@/api/endpoints";
import { genIdempotencyKey } from "@/api/client";

export default function TicketNew() {
  const { isStaff } = useAuth();
  const navigate = useNavigate();
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [modelMode, setModelMode] = useState<string>("mock");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!subject.trim() || !body.trim()) {
      setErr("主题与正文均为必填项。");
      return;
    }
    setErr(null);
    setBusy(true);
    try {
      await ticketApi.submit(
        {
          subject: subject.trim(),
          body: body.trim(),
          model_mode: isStaff ? modelMode : "mock",
        },
        genIdempotencyKey(),
      );
      navigate("/tickets");
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "提交失败");
      setBusy(false);
    }
  };

  return (
    <UserTopbar title="提交工单">
      <div className="page-narrow">
        <Alert kind="info">
          提交后会自动触发一次 Agent 运行：清洗 → 分类 → 检索 → 生成带引用的回复草稿，由坐席审核后发布。
        </Alert>
        {err && <Alert kind="danger">{err}</Alert>}

        <form onSubmit={submit}>
          <Field label="主题" hint="一句话概括你的问题，例如：订单迟迟未发货">
            <input
              className="input"
              value={subject}
              maxLength={200}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="退换货咨询 / 物流问题 / 商品使用"
            />
          </Field>
          <Field label="问题正文" hint="尽量包含订单号、时间、商品等影响判断的实体信息，不要填写密码等敏感内容">
            <textarea
              className="textarea"
              value={body}
              maxLength={8000}
              onChange={(e) => setBody(e.target.value)}
              placeholder="请描述你遇到的问题…"
            />
          </Field>
          {isStaff && (
            <Field label="运行模式（坐席可覆盖）">
              <select
                className="select"
                style={{ width: "auto" }}
                value={modelMode}
                onChange={(e) => setModelMode(e.target.value)}
              >
                <option value="mock">Mock（可控演示）</option>
                <option value="real">Real（真实模型）</option>
              </select>
            </Field>
          )}
          <div className="row">
            <button className="btn btn-primary" disabled={busy}>
              {busy ? <Spinner /> : "提交工单"}
            </button>
            <button type="button" className="btn" onClick={() => navigate("/tickets")}>
              取消
            </button>
          </div>
        </form>
      </div>
    </UserTopbar>
  );
}
