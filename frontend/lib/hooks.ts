import { useEffect, useState } from "react";

/**
 * Load data when `key` changes (and when `reload()` is called). Pass everything the request
 * depends on in `key`, for example `${id}:${query}`. `delay` debounces typing.
 * `loading` is true until the first result for the current key arrives.
 */
export function useLoad<T>(key: string, load: () => Promise<T>, delay = 0) {
  const [result, setResult] = useState<{ key: string; data?: T; error?: string }>({ key: "" });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(() => {
      load()
        .then((data) => !cancelled && setResult({ key, data }))
        .catch((e: Error) => !cancelled && setResult({ key, error: e.message }));
    }, delay);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
    // `load` is recreated every render on purpose; `key` describes what it depends on.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, tick]);

  return {
    data: result.data,
    error: result.error,
    loading: result.key !== key,
    reload: () => setTick((t) => t + 1),
  };
}
