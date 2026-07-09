import client from "./client";

export function listUsers(page = 1, limit = 20) {
  return client.get("/api/v1/users", { params: { page, limit } });
}

export function createUser(payload) {
  return client.post("/api/v1/users", payload);
}

export function updateUser(userId, payload) {
  return client.put(`/api/v1/users/${userId}`, payload);
}

export function deleteUser(userId) {
  return client.delete(`/api/v1/users/${userId}`);
}
