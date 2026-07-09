import client from "./client";

// Background removal: upload an image; the backend returns a transparent PNG.
export function submitBgRemove(file, onProgress) {
  const form = new FormData();
  form.append("file", file);
  return client.post("/api/v1/images/bg-remove", form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
}

// Image-to-shorts: upload one or more images; the backend returns a 9:16 MP4.
export function submitImageToShorts(files, onProgress) {
  const form = new FormData();
  for (const f of files) form.append("files", f);
  return client.post("/api/v1/images/to-shorts", form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
}

// Image tool (crop / resize / convert): upload an image + op + JSON params.
export function submitImageTool(file, op, params = {}, onProgress) {
  const form = new FormData();
  form.append("file", file);
  form.append("op", op);
  form.append("params", JSON.stringify(params));
  return client.post("/api/v1/images/tool", form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
}

export function getImage(imageId) {
  return client.get(`/api/v1/images/${imageId}`);
}

export function listImages(page = 1, limit = 20, { status = "" } = {}) {
  const params = { page, limit };
  if (status) params.status = status;
  return client.get("/api/v1/images", { params });
}

export function deleteImage(imageId) {
  return client.delete(`/api/v1/images/${imageId}`);
}

export function getImageStreamUrl(imageId) {
  const base = import.meta.env.VITE_API_URL ?? "";
  const token = localStorage.getItem("access_token") ?? "";
  return `${base}/api/v1/images/${imageId}/stream?token=${encodeURIComponent(token)}`;
}

export async function downloadImageBlob(imageId, filename) {
  const res = await client.get(`/api/v1/images/${imageId}/download`, { responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
