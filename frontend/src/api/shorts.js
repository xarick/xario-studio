import client from "./client";

export function getShort(shortId) {
  return client.get(`/api/v1/shorts/${shortId}`);
}

export function getShortDownloadUrl(shortId) {
  const base = import.meta.env.VITE_API_URL ?? "";
  return `${base}/api/v1/shorts/${shortId}/download`;
}

export function getShortStreamUrl(shortId) {
  const base = import.meta.env.VITE_API_URL ?? "";
  const token = localStorage.getItem("access_token") ?? "";
  return `${base}/api/v1/shorts/${shortId}/stream?token=${encodeURIComponent(token)}`;
}

export async function downloadShortBlob(shortId, filename) {
  const res = await client.get(`/api/v1/shorts/${shortId}/download`, {
    responseType: "blob",
  });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
