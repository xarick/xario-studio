import { useState, useEffect, useCallback } from "react";
import { getVideoStats } from "../api/videos";

const EMPTY = { total_videos: 0, total_shorts: 0, completed: 0, processing: 0, failed: 0 };

export function useDashboardStats() {
  const [stats, setStats] = useState(EMPTY);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const { data } = await getVideoStats();
      setStats(data);
    } catch {
      // silently fail — show zeros
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return { stats, loading, refresh };
}
