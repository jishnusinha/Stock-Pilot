import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, isConnectionError } from "../api/client";

export type LoadState<T> = {
  data: T | null;
  loading: boolean;
  error: string | null;
  offline: boolean;
  reload: () => void;
};

export function useApi<T>(
  loader: (signal: AbortSignal) => Promise<T>,
  deps: unknown[] = [],
): LoadState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const gen = useRef(0);

  const run = useCallback(() => {
    const id = ++gen.current;
    setLoading(true);
    setError(null);
    const ac = new AbortController();
    loader(ac.signal)
      .then((d) => {
        if (id !== gen.current) return;
        setData(d);
        setOffline(false);
      })
      .catch((e: unknown) => {
        if (id !== gen.current || ac.signal.aborted) return;
        if (e instanceof Error && e.name === "AbortError") return;
        setOffline(isConnectionError(e));
        const msg =
          e instanceof ApiError
            ? e.message
            : e instanceof Error
              ? e.message
              : "Request failed";
        setError(msg);
      })
      .finally(() => {
        if (id === gen.current) setLoading(false);
      });
    return () => {
      ac.abort();
    };
  }, deps);

  useEffect(() => {
    const cleanup = run();
    return cleanup;
  }, [run]);

  return { data, loading, error, offline, reload: run };
}

export function useDebouncedValue<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  // Stabilize object deps — new `{}` each render must not reset the timer forever
  const key =
    typeof value === "object" && value !== null ? JSON.stringify(value) : String(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- keyed by serialized value
  }, [key, ms]);
  return debounced;
}
