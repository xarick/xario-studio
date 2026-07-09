import { useState, useEffect, useCallback } from "react";
import { listVideos, deleteVideo } from "../api/videos";

export function useVideos({ search = "", status = "", mode = "" } = {}) {
  const [data, setData] = useState({ items: [], total: 0, page: 1, limit: 20, pages: 0 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [deleting, setDeleting] = useState(null);

  const fetchPage = useCallback(async (page = 1) => {
    setLoading(true);
    setError(null);
    try {
      const { data: res } = await listVideos(page, 20, { search, status, mode });
      setData(res);
    } catch (e) {
      setError(e?.response?.data?.detail ?? "Videolarni yuklashda xato");
    } finally {
      setLoading(false);
    }
  }, [search, status, mode]);

  useEffect(() => { fetchPage(1); }, [fetchPage]);

  async function remove(videoId) {
    if (deleting) return;
    setDeleting(videoId);
    try {
      await deleteVideo(videoId);
      setData(prev => ({
        ...prev,
        items: prev.items.filter(v => v.id !== videoId),
        total: Math.max(0, prev.total - 1),
      }));
      return { ok: true };
    } catch (e) {
      const msg = e?.response?.data?.detail ?? "O'chirishda xato";
      return { ok: false, error: msg };
    } finally {
      setDeleting(null);
    }
  }

  return { data, loading, error, deleting, fetchPage, remove };
}
