import { useState, useEffect, useCallback, useRef } from "react";
import { getNotifications, markRead, markAllRead } from "../api/notifications";

const POLL_INTERVAL = 20_000;

export function useNotifications() {
  const [items, setItems]             = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading]         = useState(false);
  const intervalRef                   = useRef(null);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const { data } = await getNotifications({ limit: 30 });
      setItems(data.items);
      setUnreadCount(data.unread_count);
    } catch {
      // silently ignore auth/network errors during polling
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    intervalRef.current = setInterval(() => load(true), POLL_INTERVAL);
    return () => clearInterval(intervalRef.current);
  }, [load]);

  const read = useCallback(async (id) => {
    try {
      await markRead(id);
      setItems(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n));
      setUnreadCount(prev => Math.max(0, prev - 1));
    } catch {}
  }, []);

  const readAll = useCallback(async () => {
    try {
      await markAllRead();
      setItems(prev => prev.map(n => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch {}
  }, []);

  return { items, unreadCount, loading, reload: load, read, readAll };
}
