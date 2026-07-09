import { useCallback, useEffect, useRef, useState } from "react";
import { getVideo } from "../api/videos";

const POLL_MS = 2500;
const MAX_RETRIES = 5;

/** Sentinel codes the hook sets in `error`; anything else is a backend message. */
const CODES = new Set(["resultError", "pollError"]);

/**
 * The message to show when a job ends badly: the backend's own explanation wins,
 * then one of our sentinels, then the page's generic fallback.
 */
export function jobErrorText(t, job, error, fallbackKey) {
  if (job?.error_message) return job.error_message;
  if (error) return CODES.has(error) ? t(`job.${error}`) : error;
  return t(fallbackKey);
}

/**
 * Drive one submitted job from `pending` to its result.
 *
 * `loadResult(jobId, job)` runs once the job completes and returns whatever the
 * page renders (a short, a list of stems, a transcript, the finished row…). It
 * MUST throw when there is nothing to show — a completed job with no result is
 * an error, not a reason to quietly send the user back to the submit form.
 *
 * `fetchJob` polls the job row. Image jobs live behind their own endpoint, so
 * the image pages pass `getImage`.
 *
 * Polling chains setTimeout rather than setInterval, so a slow request can never
 * overlap the next one, and a backend that keeps failing surfaces an error after
 * MAX_RETRIES instead of spinning forever.
 */
export function useMediaJob(loadResult, fetchJob = getVideo) {
  const [job, setJob] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const timer = useRef(null);
  const retries = useRef(0);
  const loader = useRef(loadResult);
  loader.current = loadResult;
  const fetcher = useRef(fetchJob);
  fetcher.current = fetchJob;

  const stop = useCallback(() => {
    clearTimeout(timer.current);
    timer.current = null;
  }, []);

  const reset = useCallback(() => {
    stop();
    retries.current = 0;
    setJob(null);
    setResult(null);
    setError("");
  }, [stop]);

  /** Begin tracking the job returned by a submit call. */
  const start = useCallback((submitted) => {
    if (!submitted?.id) return;
    stop();
    retries.current = 0;
    setResult(null);
    setError("");
    setJob(submitted);
  }, [stop]);

  useEffect(() => {
    const id = job?.id;
    if (!id) return undefined;

    let cancelled = false;

    async function tick() {
      if (cancelled) return;
      try {
        const { data } = await fetcher.current(id);
        if (cancelled) return;
        retries.current = 0;
        setJob(data);

        if (data.status === "failed") return;        // the page shows error_message
        if (data.status === "completed") {
          try {
            const loaded = await loader.current(id, data);
            if (!cancelled) setResult(loaded);
          } catch {
            if (!cancelled) setError("resultError");
          }
          return;
        }
      } catch (err) {
        if (cancelled) return;
        retries.current += 1;
        if (retries.current >= MAX_RETRIES) {
          setError(err?.response?.data?.detail ?? "pollError");
          return;
        }
      }
      timer.current = setTimeout(tick, POLL_MS);
    }

    tick();
    return () => {
      cancelled = true;
      clearTimeout(timer.current);
    };
    // Only the job identity restarts the loop; status changes are handled inside.
  }, [job?.id]);

  useEffect(() => stop, [stop]);

  const isProcessing =
    !!job && !error && job.status !== "completed" && job.status !== "failed";

  return { job, result, error, isProcessing, start, reset };
}
