import client from "./client";

export const authApi = {
  login: (username, password) =>
    client.post("/api/v1/auth/login", { username, password }),

  me: () =>
    client.get("/api/v1/auth/me"),

  updateMe: (payload) =>
    client.put("/api/v1/auth/me", payload),

  changePassword: (current_password, new_password) =>
    client.put("/api/v1/auth/password", { current_password, new_password }),
};
