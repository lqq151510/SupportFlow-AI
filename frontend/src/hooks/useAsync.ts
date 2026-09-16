import { useCallback, useEffect, useRef, useState } from "react";

// 数据加载：在 deps 变化时拉取，返回 data/loading/error 与 reload。
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    fn()
      .then((d) => setData(d))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    void load();
  }, [load]);

  return { data, loading, error, reload: load };
}

// 带幂等键的写操作：同一意图复用同一 Idempotency-Key（避免重复点击造成多次业务效果），
// 成功后重置，失败保留以便重试同一意图（后端相同键 + 相同内容重放返回首次结果）。
export function useMutation<TArgs extends unknown[]>(
  fn: (idemKey: string, ...args: TArgs) => Promise<unknown>,
) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const keyRef = useRef<string | null>(null);

  const run = useCallback(
    async (...args: TArgs) => {
      if (!keyRef.current) keyRef.current = genKey();
      const key = keyRef.current;
      setLoading(true);
      setError(null);
      try {
        await fn(key, ...args);
        keyRef.current = null;
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        throw e;
      } finally {
        setLoading(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [fn],
  );

  const reset = useCallback(() => {
    keyRef.current = null;
    setError(null);
  }, []);

  return { run, loading, error, reset };
}

function genKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return "idem-" + Math.random().toString(36).slice(2) + Date.now().toString(36);
}

// 单次写操作：管理 loading / error，调用期间由调用方禁用按钮以防重复提交。
export function useAction() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = useCallback(async (fn: () => Promise<unknown>) => {
    setLoading(true);
    setError(null);
    try {
      return await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);
  const clear = useCallback(() => setError(null), []);
  return { run, loading, error, clear };
}
