import { useState, useEffect, useCallback } from "react";
import { listImages, deleteImage } from "../api/images";

/** Paginated image-job list with optimistic delete. Mirrors `useVideos`. */
export function useImages({ status = "" } = {}) {
  const [data, setData] = useState({ items: [], total: 0, page: 1, limit: 20, pages: 0 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [deleting, setDeleting] = useState(null);

  const fetchPage = useCallback(async (page = 1) => {
    setLoading(true);
    setError(null);
    try {
      const { data: res } = await listImages(page, 20, { status });
      setData(res);
    } catch (e) {
      setError(e?.response?.data?.detail ?? "Rasmlarni yuklashda xato");
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => { fetchPage(1); }, [fetchPage]);

  async function remove(imageId) {
    if (deleting) return;
    setDeleting(imageId);
    try {
      await deleteImage(imageId);
      setData(prev => ({
        ...prev,
        items: prev.items.filter(i => i.id !== imageId),
        total: Math.max(0, prev.total - 1),
      }));
      return { ok: true };
    } catch (e) {
      return { ok: false, error: e?.response?.data?.detail ?? "O'chirishda xato" };
    } finally {
      setDeleting(null);
    }
  }

  return { data, loading, error, deleting, fetchPage, remove };
}
