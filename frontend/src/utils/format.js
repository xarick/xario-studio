import i18next from "i18next";

export function formatDuration(seconds) {
  if (seconds == null || isNaN(seconds)) return null;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

export function formatStatus(status) {
  return i18next.t(`status.${status}`, { defaultValue: status });
}

export function extractApiError(e) {
  const detail = e?.response?.data?.detail;
  if (!detail) return i18next.t("common.error");
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map(d => (d.msg ?? i18next.t("common.error")).replace(/^Value error,\s*/i, "")).join("; ");
  }
  return i18next.t("common.error");
}

export function timeAgo(iso) {
  if (!iso) return "";
  const s = Math.floor((Date.now() - new Date(iso)) / 1000);
  if (s < 60)    return `${s}s oldin`;
  if (s < 3600)  return `${Math.floor(s / 60)} min oldin`;
  if (s < 86400) return `${Math.floor(s / 3600)} soat oldin`;
  return new Date(iso).toLocaleDateString("uz-UZ");
}
