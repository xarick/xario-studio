import client from "./client";

export const getNotifications = (params = {}) =>
  client.get("/api/v1/notifications", { params });

export const getUnreadCount = () =>
  client.get("/api/v1/notifications/unread-count");

export const markRead = (id) =>
  client.post(`/api/v1/notifications/${id}/read`);

export const markAllRead = () =>
  client.post("/api/v1/notifications/read-all");
