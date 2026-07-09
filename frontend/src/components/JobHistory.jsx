import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  Search, Trash2, ExternalLink, Film, RefreshCw, ChevronLeft, ChevronRight, X, Wand2, MousePointer2,
  Scissors, Captions, Volume2, Mic2, Languages, FileText, Mic, Wrench,
} from "lucide-react";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { Card } from "./ui/Card";
import { Badge } from "./ui/Badge";
import { Button } from "./ui/Button";
import { Input } from "./ui/Input";
import { Select } from "./ui/Select";
import { Spinner } from "./ui/Spinner";
import { useVideos } from "../hooks/useVideos";
import { formatDuration, formatStatus, timeAgo } from "../utils/format";

const STATUS_KEYS = ["all", "completed", "processing", "downloading", "failed", "pending"];

/** Every generation mode the video table can hold. */
export const ALL_MODES = [
  "simple", "smart", "pro", "edit", "subtitle",
  "cleanup", "separate", "dub", "transcribe", "tts", "tool",
];

/** The job types the audio module produces. `cleanup`, `separate`, `dub` and
 *  `transcribe` also accept video files — the mode, not the file, defines the
 *  module, exactly as the sidebar does. */
export const AUDIO_MODES = ["tts", "dub", "cleanup", "separate", "transcribe"];

const VIOLET = "bg-violet-500/12 text-violet-300 border-violet-500/25";
const AMBER  = "bg-amber-500/12 text-amber-300 border-amber-500/25";
const NEUTRAL = "bg-white/5 text-zinc-400 border-white/12";

const MODE_META = {
  simple:     { icon: Film,          cls: NEUTRAL, label: "modeBadge.simple" },
  smart:      { icon: Wand2,         cls: VIOLET,  label: "modeBadge.smart" },
  pro:        { icon: MousePointer2, cls: AMBER,   label: "modeBadge.pro" },
  edit:       { icon: Scissors,      cls: VIOLET,  label: "modeBadge.edit" },
  subtitle:   { icon: Captions,      cls: VIOLET,  label: "modeBadge.subtitle" },
  cleanup:    { icon: Volume2,       cls: NEUTRAL, label: "modeBadge.cleanup" },
  separate:   { icon: Mic2,          cls: NEUTRAL, label: "modeBadge.separate" },
  dub:        { icon: Languages,     cls: VIOLET,  label: "modeBadge.dub" },
  transcribe: { icon: FileText,      cls: NEUTRAL, label: "modeBadge.transcribe" },
  tts:        { icon: Mic,           cls: AMBER,   label: "modeBadge.tts" },
  tool:       { icon: Wrench,        cls: NEUTRAL, label: "modeBadge.tool" },
};

function ModeBadge({ mode }) {
  const { t } = useTranslation();
  const meta = MODE_META[mode] ?? MODE_META.smart;
  const Icon = meta.icon;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md border text-[11px] font-medium whitespace-nowrap ${meta.cls}`}>
      <Icon size={11} strokeWidth={2} className="shrink-0" />
      {t(meta.label)}
    </span>
  );
}

/**
 * Paginated, searchable job list shared by the video and audio history pages.
 *
 * `modes` is both the mode-filter menu and the "all" query: the audio page asks
 * the backend for only its own job types instead of paging through every video.
 */
export function JobHistory({
  modes = ALL_MODES,
  titleKey = "history.title",
  emptyActionRoute = "/video/new",
  emptyActionKey = "history.empty.addVideo",
}) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [modeFilter, setModeFilter] = useState("all");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const debounceRef = useRef(null);

  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setDebouncedSearch(search), 400);
    return () => clearTimeout(debounceRef.current);
  }, [search]);

  // "all" within a module means every mode that module owns, not every mode.
  const modeQuery = modeFilter === "all"
    ? (modes === ALL_MODES ? "" : modes.join(","))
    : modeFilter;

  const { data, loading, error, deleting, fetchPage, remove } = useVideos({
    search: debouncedSearch,
    status: statusFilter === "all" ? "" : statusFilter,
    mode: modeQuery,
  });

  const modeOptions = ["all", ...modes].map(m => ({
    value: m,
    label: m === "all" ? t("history.allModes") : t(MODE_META[m]?.label ?? m),
  }));

  const filtered = search || statusFilter !== "all" || modeFilter !== "all";

  async function handleDelete(id, e) {
    e.stopPropagation();
    const result = await remove(id);
    if (result?.ok) toast.success(t("history.deleted"));
    else if (result?.error) toast.error(result.error);
  }

  function clearSearch() {
    setSearch("");
    setDebouncedSearch("");
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">{t(titleKey)}</h1>
          <p className="text-zinc-500 mt-1 text-sm">
            {loading
              ? t("common.loading")
              : data.total > 0
              ? t("history.total", { count: data.total })
              : t("history.noVideos")}
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={() => fetchPage(data.page ?? 1)} disabled={loading}>
          <RefreshCw size={14} className={loading ? "spin" : ""} />
          {t("common.refresh")}
        </Button>
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <div className="flex-1 relative">
          <Input
            placeholder={t("common.search")}
            icon={Search}
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          {search && (
            <button
              onClick={clearSearch}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-600 hover:text-zinc-300 transition-colors"
            >
              <X size={14} />
            </button>
          )}
        </div>
        <Select
          value={modeFilter}
          onChange={setModeFilter}
          options={modeOptions}
          icon={Wrench}
          className="sm:w-44"
        />
        <div className="flex flex-wrap gap-1.5">
          {STATUS_KEYS.map(s => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-1.5 rounded-lg text-[12px] font-medium border transition-all
                ${statusFilter === s
                  ? "bg-violet-500/15 border-violet-500/30 text-violet-400"
                  : "bg-white/3 border-white/8 text-zinc-500 hover:text-zinc-300 hover:bg-white/6"
                }`}
            >
              {s === "all" ? t("common.all") : formatStatus(s)}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="rounded-xl bg-red-500/8 border border-red-500/18 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {loading && (
        <div className="flex items-center gap-2 text-zinc-600 text-sm py-2">
          <Spinner size={16} className="text-violet-400" /> {t("common.loading")}
        </div>
      )}

      {!loading && data.items.length === 0 && (
        <Card>
          <div className="flex flex-col items-center gap-4 py-14 text-center">
            <div className="w-14 h-14 rounded-2xl bg-white/3 border border-white/8 flex items-center justify-center">
              <Film size={22} className="text-zinc-600" />
            </div>
            <div>
              <p className="font-medium text-zinc-400">
                {filtered ? t("history.empty.notFound") : t("history.empty.noVideos")}
              </p>
              {filtered ? (
                <button
                  onClick={() => { clearSearch(); setStatusFilter("all"); setModeFilter("all"); }}
                  className="text-sm text-violet-400 hover:text-violet-300 transition-colors mt-1"
                >
                  {t("history.empty.clearFilter")}
                </button>
              ) : (
                <p className="text-sm text-zinc-600 mt-1">{t("history.empty.addFirst")}</p>
              )}
            </div>
            {!filtered && (
              <Button size="sm" onClick={() => navigate(emptyActionRoute)}>{t(emptyActionKey)}</Button>
            )}
          </div>
        </Card>
      )}

      {data.items.length > 0 && (
        <>
          <div className="hidden sm:grid gap-4 px-5 text-[11px] text-zinc-600 uppercase tracking-wider font-semibold"
            style={{ gridTemplateColumns: "minmax(0,1fr) 116px 52px 76px 92px 158px" }}>
            <span>{t("history.table.video")}</span>
            <span>{t("history.table.mode")}</span>
            <span>{t("history.table.shorts")}</span>
            <span>{t("history.table.duration")}</span>
            <span>{t("history.table.date")}</span>
            <span>{t("history.table.status")}</span>
          </div>

          <div className="flex flex-col gap-1.5">
            {data.items.map(v => {
              const isDeleting = deleting === v.id;
              return (
                <div
                  key={v.id}
                  onClick={() => navigate(`/job/${v.id}`)}
                  className={`table-row group ${isDeleting ? "opacity-50 pointer-events-none" : ""}`}
                  style={{ gridTemplateColumns: "minmax(0,1fr) 116px 52px 76px 92px 158px" }}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                      v.status === "completed" ? "bg-emerald-400" :
                      v.status === "failed"    ? "bg-red-400" :
                      v.status === "pending"   ? "bg-zinc-600" :
                      "bg-amber-400 status-dot-pulse"
                    }`} />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-zinc-200 truncate">
                        {v.original_filename ?? v.source_url ?? "Video"}
                      </p>
                      <p className="text-[11px] text-zinc-600 sm:hidden mt-0.5 flex items-center gap-1.5">
                        <ModeBadge mode={v.generation_mode} />
                        <span>· {v.shorts_requested} short · {timeAgo(v.created_at)}</span>
                      </p>
                    </div>
                  </div>

                  <div className="hidden sm:flex items-center">
                    <ModeBadge mode={v.generation_mode} />
                  </div>

                  <div className="text-sm text-zinc-500 hidden sm:block tabular-nums">{v.shorts_requested}</div>
                  <div className="text-sm text-zinc-500 hidden sm:block">{formatDuration(v.duration_seconds) ?? "—"}</div>
                  <div className="text-[12px] text-zinc-600 hidden sm:block">{timeAgo(v.created_at)}</div>

                  <div className="flex items-center justify-end sm:justify-start gap-2">
                    <Badge status={v.status} />
                    <button
                      onClick={e => handleDelete(v.id, e)}
                      disabled={isDeleting}
                      title={t("common.delete")}
                      className={`opacity-0 group-hover:opacity-100 p-1.5 rounded-lg transition-all
                        ${isDeleting
                          ? "text-zinc-600 cursor-not-allowed"
                          : "text-zinc-700 hover:text-red-400 hover:bg-red-500/10"
                        }`}
                    >
                      {isDeleting ? <Spinner size={13} /> : <Trash2 size={13} />}
                    </button>
                    <ExternalLink size={11} className="text-zinc-700 hidden sm:block shrink-0" />
                  </div>
                </div>
              );
            })}
          </div>

          {data.pages > 1 && (
            <div className="flex items-center justify-center gap-2 pt-2">
              <button
                onClick={() => fetchPage(data.page - 1)}
                disabled={data.page <= 1}
                className="w-8 h-8 rounded-lg flex items-center justify-center border border-white/8 text-zinc-500 hover:text-zinc-300 hover:bg-white/6 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
              >
                <ChevronLeft size={15} />
              </button>
              {Array.from({ length: data.pages }, (_, i) => i + 1).map(p => (
                <button
                  key={p}
                  onClick={() => fetchPage(p)}
                  className={`w-8 h-8 rounded-lg text-sm font-medium transition-all
                    ${p === data.page
                      ? "bg-violet-600 text-white shadow-lg shadow-violet-500/25"
                      : "border border-white/8 text-zinc-500 hover:text-zinc-300 hover:bg-white/6"
                    }`}
                >
                  {p}
                </button>
              ))}
              <button
                onClick={() => fetchPage(data.page + 1)}
                disabled={data.page >= data.pages}
                className="w-8 h-8 rounded-lg flex items-center justify-center border border-white/8 text-zinc-500 hover:text-zinc-300 hover:bg-white/6 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
              >
                <ChevronRight size={15} />
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
