import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Images, Trash2, RefreshCw, ChevronLeft, ChevronRight, Scissors, Film,
  Crop, Maximize, Wand2, ZoomIn, Download,
} from "lucide-react";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Spinner } from "../components/ui/Spinner";
import { useImages } from "../hooks/useImages";
import { formatStatus, timeAgo } from "../utils/format";
import { getImageStreamUrl, downloadImageBlob } from "../api/images";

const STATUS_KEYS = ["all", "completed", "processing", "failed", "pending"];

const OP_META = {
  bg_remove:       { icon: Scissors,  label: "imageHistory.op.bgRemove" },
  image_to_shorts: { icon: Film,      label: "imageHistory.op.toShorts" },
  crop:            { icon: Crop,      label: "imageHistory.op.crop" },
  resize:          { icon: Maximize,  label: "imageHistory.op.resize" },
  convert:         { icon: RefreshCw, label: "imageHistory.op.convert" },
  enhance:         { icon: Wand2,     label: "imageHistory.op.enhance" },
  upscale:         { icon: ZoomIn,    label: "imageHistory.op.upscale" },
};

function OpBadge({ operation }) {
  const { t } = useTranslation();
  const meta = OP_META[operation];
  if (!meta) return <span className="text-[11px] text-zinc-500">{operation}</span>;
  const Icon = meta.icon;
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md border text-[11px] font-medium
      whitespace-nowrap bg-rose-500/12 text-rose-300 border-rose-500/25">
      <Icon size={11} strokeWidth={2} className="shrink-0" />
      {t(meta.label)}
    </span>
  );
}

/** image_to_shorts produces an MP4; everything else is a still. */
const isVideoResult = job => job.output_ext === "mp4";

export default function ImageHistoryPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState("all");
  const { data, loading, error, deleting, fetchPage, remove } = useImages({
    status: statusFilter === "all" ? "" : statusFilter,
  });

  async function handleDelete(id) {
    const result = await remove(id);
    if (result?.ok) toast.success(t("history.deleted"));
    else if (result?.error) toast.error(result.error);
  }

  async function handleDownload(job) {
    await downloadImageBlob(job.id, `${job.operation}.${job.output_ext ?? "png"}`);
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">{t("images.historyTitle")}</h1>
          <p className="text-zinc-500 mt-1 text-sm">
            {loading ? t("common.loading") : t("history.total", { count: data.total })}
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={() => fetchPage(data.page ?? 1)} disabled={loading}>
          <RefreshCw size={14} className={loading ? "spin" : ""} />
          {t("common.refresh")}
        </Button>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {STATUS_KEYS.map(s => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`px-3 py-1.5 rounded-lg text-[12px] font-medium border transition-all
              ${statusFilter === s
                ? "bg-rose-500/15 border-rose-500/30 text-rose-400"
                : "bg-white/3 border-white/8 text-zinc-500 hover:text-zinc-300 hover:bg-white/6"
              }`}
          >
            {s === "all" ? t("common.all") : formatStatus(s)}
          </button>
        ))}
      </div>

      {error && (
        <div className="rounded-xl bg-red-500/8 border border-red-500/18 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {loading && (
        <div className="flex items-center gap-2 text-zinc-600 text-sm py-2">
          <Spinner size={16} className="text-rose-400" /> {t("common.loading")}
        </div>
      )}

      {!loading && data.items.length === 0 && (
        <Card>
          <div className="flex flex-col items-center gap-4 py-14 text-center">
            <div className="w-14 h-14 rounded-2xl bg-white/3 border border-white/8 flex items-center justify-center">
              <Images size={22} className="text-zinc-600" />
            </div>
            <p className="font-medium text-zinc-400">{t("imageHistory.empty")}</p>
            {statusFilter === "all" && (
              <Button size="sm" onClick={() => navigate("/image/new")}>{t("imageHistory.addFirst")}</Button>
            )}
          </div>
        </Card>
      )}

      {data.items.length > 0 && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data.items.map(job => {
              const isDeleting = deleting === job.id;
              const done = job.status === "completed" && job.output_ext;
              return (
                <Card key={job.id} className={isDeleting ? "opacity-50 pointer-events-none" : ""}>
                  <div className="flex flex-col gap-3">
                    <div className="rounded-xl overflow-hidden bg-black/30 h-40 flex items-center justify-center">
                      {done ? (
                        isVideoResult(job)
                          ? <video src={getImageStreamUrl(job.id)} controls className="max-h-40 max-w-full" />
                          : <img src={getImageStreamUrl(job.id)} alt="" className="max-h-40 max-w-full object-contain" />
                      ) : (
                        <Images size={28} className="text-zinc-700" />
                      )}
                    </div>

                    <div className="flex items-center justify-between gap-2">
                      <OpBadge operation={job.operation} />
                      <Badge status={job.status} />
                    </div>

                    <p className="text-[11px] text-zinc-600 truncate">
                      {job.original_filename ?? "—"} · {timeAgo(job.created_at)}
                    </p>

                    {job.error_message && (
                      <p className="text-[11px] text-red-400/80 line-clamp-2">{job.error_message}</p>
                    )}

                    <div className="flex items-center gap-2">
                      {done && (
                        <Button variant="secondary" size="sm" className="flex-1" onClick={() => handleDownload(job)}>
                          <Download size={13} /> {t("job.download")}
                        </Button>
                      )}
                      <button
                        onClick={() => handleDelete(job.id)}
                        disabled={isDeleting}
                        title={t("common.delete")}
                        className="p-2 rounded-lg text-zinc-700 hover:text-red-400 hover:bg-red-500/10 transition-all"
                      >
                        {isDeleting ? <Spinner size={13} /> : <Trash2 size={13} />}
                      </button>
                    </div>
                  </div>
                </Card>
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
                      ? "bg-rose-600 text-white shadow-lg shadow-rose-500/25"
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
