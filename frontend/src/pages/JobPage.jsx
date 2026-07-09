import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Download, ArrowLeft, CheckCircle2, XCircle, Clock, Play, Clapperboard, RefreshCw, Music, Image as ImageIcon, Ban } from "lucide-react";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Spinner } from "../components/ui/Spinner";
import { useJob } from "../hooks/useJob";
import { formatDuration, formatStatus } from "../utils/format";
import { getShortStreamUrl, downloadShortBlob } from "../api/shorts";
import { cancelVideo } from "../api/videos";

function StepBar({ status }) {
  const { t } = useTranslation();
  const STEPS = [
    { key: "pending",     label: t("job.steps.pending") },
    { key: "downloading", label: t("job.steps.downloading") },
    { key: "processing",  label: t("job.steps.processing") },
    { key: "completed",   label: t("job.steps.completed") },
  ];
  const stepIndex = { pending: 0, downloading: 1, processing: 2, completed: 3 };
  const current = status === "failed" ? -1 : (stepIndex[status] ?? 0);

  return (
    <div className="flex items-center">
      {STEPS.map((step, i) => {
        const done   = current > i || (status === "completed");
        const active = current === i && status !== "failed" && status !== "completed";
        return (
          <div key={step.key} className="flex items-center flex-1 last:flex-none">
            <div className="flex flex-col items-center gap-1.5">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold
                border-2 transition-all duration-300
                ${done   ? "bg-emerald-500 border-emerald-500 text-white shadow-md shadow-emerald-500/30" : ""}
                ${active ? "border-violet-500 bg-violet-500/15 text-violet-400" : ""}
                ${!done && !active ? "border-white/10 bg-white/3 text-zinc-600" : ""}
              `}>
                {done ? <CheckCircle2 size={16} strokeWidth={2.5} /> : active ? <Spinner size={14} className="text-violet-400" /> : i + 1}
              </div>
              <span className={`text-[10px] font-medium whitespace-nowrap tracking-wide
                ${active ? "text-violet-400" : done ? "text-emerald-400" : "text-zinc-700"}`}>
                {step.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={`flex-1 h-0.5 mx-2 mb-4 rounded-full transition-all duration-500
                ${done ? "bg-gradient-to-r from-emerald-500 to-emerald-400" : "bg-white/6"}`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

// Mode → result noun. Falls back to the output kind (video/audio/image) so any
// new mode still gets a sensible label instead of the generic "Short".
const RESULT_KEY = {
  simple: "short", smart: "short", pro: "short",
  edit: "video", subtitle: "video",
  dub: "dub", tts: "audio", separate: "track",
};
function resultBase(t, mode, kind) {
  return t(`result.${RESULT_KEY[mode] || kind || "file"}`);
}

function ShortCard({ short, mode, multiple }) {
  const { t } = useTranslation();
  const done = short.status === "completed";
  const kind = short.kind || "video";
  const [playing, setPlaying] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const base = resultBase(t, mode, kind);
  const label = multiple ? `${base} ${short.index_number}` : base;
  const ext = short.ext || (kind === "audio" ? "mp3" : kind === "image" ? "png" : "mp4");

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const name = `${base.replace(/\s+/g, "_").toLowerCase()}_${short.index_number}.${ext}`;
      await downloadShortBlob(short.id, name);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className={`glass flex flex-col gap-3 p-4 transition-all ${done ? "glass-hover" : ""}`}>
      {/* ── Media area (chooses player by output kind) ── */}
      {kind === "audio" ? (
        <div className="flex items-center gap-3 rounded-xl p-3 border border-white/5
          bg-gradient-to-br from-violet-900/20 via-indigo-900/15 to-zinc-900/30 min-h-[64px]">
          <div className="w-10 h-10 rounded-lg bg-violet-500/15 border border-violet-500/20 flex items-center justify-center shrink-0">
            <Music size={18} className="text-violet-300" />
          </div>
          {done
            ? <audio className="w-full h-9" controls src={getShortStreamUrl(short.id)} />
            : <span className="text-[11px] text-zinc-600">{t("job.preparing")}</span>}
        </div>
      ) : kind === "image" ? (
        <div className="w-full aspect-video rounded-xl overflow-hidden bg-black/30 border border-white/5 flex items-center justify-center">
          {done
            ? <img src={getShortStreamUrl(short.id)} alt={label} className="w-full h-full object-contain" />
            : <Spinner size={18} className="text-zinc-600" />}
        </div>
      ) : (
        <div className="w-full aspect-video rounded-xl overflow-hidden relative
          bg-gradient-to-br from-violet-900/20 via-indigo-900/15 to-zinc-900/30 border border-white/5">
          {done && playing ? (
            <video className="w-full h-full object-contain bg-black" src={getShortStreamUrl(short.id)} controls autoPlay />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center">
              {done ? (
                <button onClick={() => setPlaying(true)}
                  className="w-10 h-10 rounded-full bg-white/10 backdrop-blur flex items-center justify-center hover:bg-white/20 transition-colors">
                  <Play size={16} className="text-white ml-0.5" fill="white" />
                </button>
              ) : (
                <div className="flex flex-col items-center gap-2">
                  <Spinner size={18} className="text-zinc-600" />
                  <span className="text-[10px] text-zinc-700">{t("job.preparing")}</span>
                </div>
              )}
            </div>
          )}
          {multiple && (
            <div className="absolute top-2 left-2 px-2 py-0.5 rounded-md bg-black/50 backdrop-blur text-[10px] font-semibold text-zinc-300">
              #{short.index_number}
            </div>
          )}
        </div>
      )}

      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-zinc-200 flex items-center gap-1.5">
            {kind === "audio" && <Music size={13} className="text-violet-400 shrink-0" />}
            {kind === "image" && <ImageIcon size={13} className="text-violet-400 shrink-0" />}
            {label}
          </p>
          <p className="text-[11px] text-zinc-600 mt-0.5">
            {formatDuration(short.start_time) ?? "0s"} — {formatDuration(short.end_time) ?? "?"}
            {short.duration_seconds != null && (
              <>{" · "}<span className="text-zinc-500">{formatDuration(short.duration_seconds)}</span></>
            )}
          </p>
        </div>
        <Badge status={short.status} />
      </div>

      {done && short.clips && short.clips.length > 1 && (
        <div className="flex flex-wrap gap-1">
          {short.clips.map((c, i) => (
            <span key={i} className="text-[10px] px-2 py-0.5 rounded-full bg-violet-500/10 border border-violet-500/15 text-violet-400 tabular-nums">
              {formatDuration(c.start)}–{formatDuration(c.end)}
            </span>
          ))}
        </div>
      )}

      {done && (
        <Button variant="outline" size="sm" className="w-full" onClick={handleDownload} disabled={downloading}>
          {downloading ? <Spinner size={13} /> : <Download size={13} />}
          {downloading ? t("job.downloading") : t("job.download")}
        </Button>
      )}
    </div>
  );
}

const ACTIVE = new Set(["pending", "downloading", "processing"]);

export default function JobPage() {
  const { videoId } = useParams();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { video, shorts, error } = useJob(videoId);
  const [cancelling, setCancelling] = useState(false);

  async function handleCancel() {
    if (cancelling || !window.confirm(t("job.cancelConfirm"))) return;
    setCancelling(true);
    try {
      await cancelVideo(videoId);
      toast.success(t("job.cancelled"));
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? t("common.error"));
    } finally {
      setCancelling(false);
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-3xl mx-auto">
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-1.5 text-sm text-zinc-600 hover:text-zinc-300 transition-colors w-fit"
      >
        <ArrowLeft size={15} /> {t("job.back")}
      </button>

      {error && (
        <div className="flex items-center gap-2.5 p-4 rounded-xl bg-red-500/8 border border-red-500/18 text-sm text-red-400">
          <XCircle size={16} /> {error}
        </div>
      )}

      {!video && !error && (
        <Card>
          <div className="flex items-center gap-3 text-zinc-500 text-sm">
            <Spinner className="text-violet-400" />
            <span>{t("job.loading")}</span>
          </div>
        </Card>
      )}

      {video && (
        <>
          <Card>
            <div className="flex flex-col gap-5">
              <div className="flex items-start gap-4 justify-between">
                <div className="flex items-start gap-3 min-w-0">
                  <div className="w-9 h-9 rounded-xl bg-violet-500/12 border border-violet-500/20 flex items-center justify-center shrink-0 mt-0.5">
                    <Clapperboard size={16} className="text-violet-400" />
                  </div>
                  <div className="min-w-0">
                    <p className="font-medium text-zinc-200 truncate text-sm leading-snug">
                      {video.original_filename ?? video.source_url ?? "Video"}
                    </p>
                    <p className="text-[11px] text-zinc-600 mt-1 flex flex-wrap gap-2">
                      <span className="flex items-center gap-1"><Clock size={10} />{new Date(video.created_at).toLocaleString("uz-UZ")}</span>
                      {video.duration_seconds && <span>· {formatDuration(video.duration_seconds)}</span>}
                      <span>· {video.shorts_requested} {t("job.shortsRequested")}</span>
                    </p>
                  </div>
                </div>
                <Badge status={video.status} />
              </div>

              {video.status !== "failed" && (
                <div>
                  <div className="flex justify-between text-[11px] text-zinc-600 mb-1.5">
                    <span>{formatStatus(video.status)}</span>
                    <span className="tabular-nums">{video.progress_percent}%</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-white/5 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-700
                        ${video.status === "completed" ? "bg-emerald-500" : "progress-pulse"}`}
                      style={{ width: `${video.progress_percent}%` }}
                    />
                  </div>
                </div>
              )}

              <div className="pt-1">
                <StepBar status={video.status} />
              </div>

              {video.error_message && (
                <div className="flex items-start gap-2.5 rounded-xl bg-red-500/8 border border-red-500/18 px-4 py-3 text-sm text-red-400">
                  <XCircle size={15} className="shrink-0 mt-0.5" />
                  <span>{video.error_message}</span>
                </div>
              )}
            </div>
          </Card>

          {shorts.length > 0 && (
            <div>
              <p className="text-xs text-zinc-500 uppercase tracking-widest font-semibold mb-3">
                {t("job.resultsReady", { count: shorts.length })}
              </p>
              <div className="grid sm:grid-cols-2 gap-3">
                {shorts.map(s => (
                  <ShortCard key={s.id} short={s} mode={video.generation_mode} multiple={shorts.length > 1} />
                ))}
              </div>
            </div>
          )}

          {ACTIVE.has(video.status) && (
            <Button variant="secondary" onClick={handleCancel} disabled={cancelling}>
              {cancelling ? <Spinner size={14} /> : <Ban size={14} />} {t("job.cancel")}
            </Button>
          )}

          {video.status === "failed" && (
            <Button variant="secondary" onClick={() => navigate("/video/new")}>
              <RefreshCw size={14} /> {t("job.retry")}
            </Button>
          )}
        </>
      )}
    </div>
  );
}
