import type { RunEventView } from "@/hooks/useRunEvents";

function pv(p: Record<string, unknown>, k: string): string {
  const v = p[k];
  if (v == null) return "";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

// 把后端 SSE 事件转换为给人看的一句话摘要。
export function describeEvent(ev: RunEventView): string {
  const p = ev.payload ?? {};
  switch (ev.type) {
    case "run.step.started":
    case "run.step.completed":
      return `节点：${pv(p, "node")}`;
    case "retrieval.completed":
      return `检索命中 ${pv(p, "count") || "?"} 条（RRF 融合后 Top5）`;
    case "tool.requested":
      return `调用工具 ${pv(p, "tool_name")}（风险 ${pv(p, "risk_level")}）`;
    case "tool.completed":
      return `工具 ${pv(p, "tool_name")} 完成`;
    case "draft.created":
      return `生成草稿（v${pv(p, "version")}），引用 ${pv(p, "citation_count") || "若干"} 条`;
    case "approval.required":
      return `需人工审批：${pv(p, "action_type")}`;
    case "action.executed":
      return `已执行：${pv(p, "action_type")}`;
    case "run.needs_human":
      return `转人工：${pv(p, "reason") || "证据不足"}`;
    case "run.completed":
      return "运行完成";
    case "run.failed":
      return `运行失败：${pv(p, "error_code") || "未知"}`;
    default:
      return pv(p, "detail") || "";
  }
}
