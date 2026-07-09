import client from "./client";

export function getAiSettings() {
  return client.get("/api/v1/settings/ai");
}
