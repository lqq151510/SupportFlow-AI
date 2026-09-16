import { useEffect, useRef, useState } from "react";

// 后端 SSE 数据帧：data 为 JSON { id, run_id, type, payload, created_at }；
// 控制帧：event: stream.closed，data: { status, reason }。
// EventSource 在重连时会自动带 Last-Event-ID，后端据此续传，不会重复生成事件。
export interface RunEventView {
  id: number;
  run_id: string;
  type: string;
  payload: Record<string, unknown>;
  created_at: string;
}

const EVENT_TYPES = [
  "run.started",
  "run.step.started",
  "run.step.completed",
  "retrieval.completed",
  "tool.requested",
  "tool.completed",
  "draft.created",
  "citation.invalid",
  "approval.required",
  "action.executed",
  "run.needs_human",
  "run.completed",
  "run.failed",
];

export interface RunEventStream {
  events: RunEventView[];
  connected: boolean;
  terminal: boolean;
  lastReason: string | null;
}

export function useRunEvents(runId: string | null, enabled = true): RunEventStream {
  const [events, setEvents] = useState<RunEventView[]>([]);
  const [connected, setConnected] = useState(false);
  const [terminal, setTerminal] = useState(false);
  const [lastReason, setLastReason] = useState<string | null>(null);
  const seenRef = useRef<Set<number>>(new Set());

  useEffect(() => {
    if (!runId || !enabled) return;
    setEvents([]);
    setConnected(false);
    setTerminal(false);
    setLastReason(null);
    seenRef.current = new Set();

    const source = new EventSource(`/api/v1/runs/${runId}/events`);

    const handleEvent = (ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data) as RunEventView;
        if (typeof data.id === "number" && seenRef.current.has(data.id)) return;
        if (typeof data.id === "number") seenRef.current.add(data.id);
        setEvents((prev) => [...prev, data]);
      } catch {
        /* 忽略无法解析的帧（如心跳） */
      }
    };

    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    for (const type of EVENT_TYPES) {
      source.addEventListener(type, handleEvent as EventListener);
    }
    source.addEventListener("stream.closed", (ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data) as { status: string | null; reason: string };
        setLastReason(data.reason);
        if (data.reason === "terminal") {
          setTerminal(true);
          source.close();
        }
      } catch {
        /* ignore */
      }
    });

    return () => {
      source.close();
    };
  }, [runId, enabled]);

  return { events, connected, terminal, lastReason };
}
