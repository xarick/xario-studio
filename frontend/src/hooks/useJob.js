import { useState, useEffect, useRef, useCallback } from "react";
import { getVideo, getVideoShorts } from "../api/videos";

const TERMINAL = new Set(["completed", "failed"]);
const POLL_MS  = 2500;
const MAX_RETRIES = 5;

export function useJob(videoId) {
  const [video, setVideo]   = useState(null);
  const [shorts, setShorts] = useState([]);
  const [error, setError]   = useState(null);
  const timerRef  = useRef(null);
  const retries   = useRef(0);

  const poll = useCallback(async () => {
    try {
      const { data: v } = await getVideo(videoId);
      setVideo(v);
      retries.current = 0;

      if (TERMINAL.has(v.status)) {
        clearTimeout(timerRef.current);
        if (v.status === "completed") {
          try {
            const { data: s } = await getVideoShorts(videoId);
            setShorts(s);
          } catch {
            setError("Shortlarni yuklashda xato. Sahifani yangilang.");
          }
        }
        return;
      }
    } catch (e) {
      retries.current += 1;
      if (retries.current >= MAX_RETRIES) {
        clearTimeout(timerRef.current);
        setError(e?.response?.data?.detail ?? "Ma'lumot olishda xato");
        return;
      }
    }

    timerRef.current = setTimeout(poll, POLL_MS);
  }, [videoId]);

  useEffect(() => {
    if (!videoId) return;
    poll();
    return () => clearTimeout(timerRef.current);
  }, [poll, videoId]);

  return { video, shorts, error };
}
