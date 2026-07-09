import { useState, useRef } from "react";
import { useParams, useLocation, Navigate, Link } from "react-router-dom";
import {
  Upload, Download, Loader2, RotateCcw, AlertCircle, ArrowLeft, FileVideo, FileAudio,
} from "lucide-react";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { ToolFields } from "../components/ToolFields";
import { getTool, defaultParams, ACCENTS } from "../config/tools";
import { uploadToolMedia, getVideoShorts } from "../api/videos";
import { useMediaJob, jobErrorText } from "../hooks/useMediaJob";
import { downloadShortBlob, getShortStreamUrl } from "../api/shorts";
import { extractApiError } from "../utils/format";

const VIDEO_RE = /\.(mp4|mov|avi|mkv|webm|m4v)$/i;
const AUDIO_RE = /\.(mp3|wav|m4a|aac|ogg|flac|opus)$/i;

function resultKind(path = "") {
  if (/\.gif$/i.test(path)) return "image";
  if (/\.mp4$/i.test(path)) return "video";
  return "audio";
}


/** A completed job always has exactly one short — its absence is an error. */
async function loadShort(jobId) {
  const { data } = await getVideoShorts(jobId);
  const short = (data ?? [])[0];
  if (!short) throw new Error("no short");
  return short;
}

export default function ToolRunnerPage() {
  const { t } = useTranslation();
  const { op } = useParams();
  const { pathname } = useLocation();
  const section = pathname.startsWith("/audio") ? "audio" : "video";
  const tool = getTool(section, op);

  const [file, setFile] = useState(null);
  const [extraFile, setExtraFile] = useState(null);
  const [params, setParams] = useState(() => (tool ? defaultParams(tool) : {}));
  const [dragOver, setDragOver] = useState(false);
  const extraRef = useRef(null);
  const [loading, setLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState("");
  const [localError, setLocalError] = useState("");
  const { job, result, error: jobError, isProcessing, start, reset: resetJob } =
    useMediaJob(loadShort);
  const fileRef = useRef(null);


  if (!tool) return <Navigate to="/tools" replace />;

  const accent = ACCENTS[tool.accent] ?? ACCENTS.violet;
  const isAudio = section === "audio";
  const Icon = tool.icon;

  function isAllowed(f) {
    if (!f) return false;
    return isAudio ? f.type.startsWith("audio/") || AUDIO_RE.test(f.name)
                   : f.type.startsWith("video/") || VIDEO_RE.test(f.name);
  }
  function pickFile(f) {
    if (isAllowed(f)) { setFile(f); setLocalError(""); }
    else toast.error(t(isAudio ? "media.onlyAudio" : "media.onlyVideo"));
  }
  function setParam(k, v) { setParams(p => ({ ...p, [k]: v })); }

  async function handleSubmit(e) {
    e.preventDefault();
    setLocalError(""); setError("");
    if (!file) { setLocalError(t("newVideo.errors.noFile")); return; }
    if (tool.extraFile && !extraFile) { setLocalError(t("toolRun.needLogo")); return; }
    setLoading(true); setUploadProgress(0);
    try {
      const { data } = await uploadToolMedia(file, tool.op, params, setUploadProgress, extraFile);
      start(data);
    } catch (err) {
      setError(extractApiError(err));
    } finally {
      setLoading(false);
    }
  }

  function reset() { resetJob(); setFile(null); setExtraFile(null); setLocalError(""); setError(""); }

  async function download() {
    if (!result) return;
    const ext = (result.file_path || "").split(".").pop() || "out";
    const base = (file?.name || tool.id).replace(/\.[^.]+$/, "");
    await downloadShortBlob(result.id, `${base}_${tool.id}.${ext}`);
  }

  const kind = resultKind(result?.file_path);

  return (
    <div className="max-w-xl mx-auto flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-start gap-3">
        <Link to="/tools" className="mt-1 text-zinc-600 hover:text-zinc-300 transition-colors">
          <ArrowLeft size={18} />
        </Link>
        <div className={`w-11 h-11 rounded-xl ${accent.bg} border ${accent.border} flex items-center justify-center shrink-0`}>
          <Icon size={20} className={accent.text} strokeWidth={1.8} />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">{t(`toolDefs.${tool.id}.name`)}</h1>
          <p className="text-zinc-500 mt-1 text-sm">{t(`toolDefs.${tool.id}.desc`)}</p>
        </div>
      </div>

      {job?.status === "completed" && result ? (
        <Card>
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-emerald-400">{t("toolRun.done")}</span>
              <button onClick={reset} className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 transition-colors">
                <RotateCcw size={13} /> {t("toolRun.new")}
              </button>
            </div>
            {kind === "video" && <video src={getShortStreamUrl(result.id)} controls className="w-full rounded-xl bg-black max-h-[360px]" />}
            {kind === "image" && <img src={getShortStreamUrl(result.id)} alt="result" className="w-full rounded-xl bg-black max-h-[360px] object-contain" />}
            {kind === "audio" && <audio src={getShortStreamUrl(result.id)} controls className="w-full" />}
            <Button onClick={download} size="lg"><Download size={18} /> {t("toolRun.download")}</Button>
          </div>
        </Card>
      ) : (job?.status === "failed" || jobError) ? (
        <Card>
          <div className="flex flex-col items-center gap-4 py-10 text-center">
            <AlertCircle size={32} className="text-red-400" />
            <p className="text-sm text-zinc-400">{jobErrorText(t, job, jobError, "toolRun.failed")}</p>
            <Button size="sm" variant="secondary" onClick={reset}>{t("toolRun.new")}</Button>
          </div>
        </Card>
      ) : isProcessing ? (
        <Card>
          <div className="flex flex-col items-center gap-4 py-12 text-center">
            <Loader2 size={32} className={`${accent.text} animate-spin`} />
            <div>
              <p className="font-medium text-zinc-200">{t("toolRun.processing")}</p>
              <p className="text-sm text-zinc-600 mt-1">{t("toolRun.processingHint")} · {job.progress_percent ?? 0}%</p>
            </div>
          </div>
        </Card>
      ) : (
        <Card>
          <form onSubmit={handleSubmit} className="flex flex-col gap-6">
            {/* Upload */}
            <div
              onDragOver={e => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={e => { e.preventDefault(); setDragOver(false); pickFile(e.dataTransfer.files[0]); }}
              onClick={() => fileRef.current?.click()}
              className={`flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed
                p-10 cursor-pointer transition-all duration-200
                ${dragOver ? "drag-over" : "border-white/10 hover:border-violet-500/30 hover:bg-violet-500/3"}
                ${file ? "border-emerald-500/30 bg-emerald-500/5" : ""}`}
            >
              <input ref={fileRef} type="file" accept={isAudio ? "audio/*" : "video/*"} className="hidden"
                onChange={e => e.target.files[0] && pickFile(e.target.files[0])} />
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center
                ${file ? "bg-emerald-500/15" : `${accent.bg} border ${accent.border}`}`}>
                {file ? (isAudio ? <FileAudio size={22} className="text-emerald-400" /> : <FileVideo size={22} className="text-emerald-400" />)
                      : <Upload size={22} className={accent.text} />}
              </div>
              {file ? (
                <div className="text-center">
                  <p className="font-medium text-zinc-200 text-sm">{file.name}</p>
                  <p className="text-xs text-zinc-500 mt-0.5">{(file.size/1024/1024).toFixed(1)} MB</p>
                </div>
              ) : (
                <div className="text-center">
                  <p className="text-sm text-zinc-400">{t(isAudio ? "media.dropAudio" : "media.dropVideo")}</p>
                  <p className="text-xs text-zinc-600 mt-1">{t(isAudio ? "media.formatsAudio" : "media.formatsVideo")}</p>
                </div>
              )}
            </div>

            {tool.extraFile && (
              <div className="flex items-center justify-between gap-4">
                <label className="text-sm font-medium text-zinc-300">{t(tool.extraFile.label)}</label>
                <input ref={extraRef} type="file" accept={tool.extraFile.accept} className="hidden"
                  onChange={e => e.target.files[0] && setExtraFile(e.target.files[0])} />
                <button type="button" onClick={() => extraRef.current?.click()}
                  className={`max-w-[55%] truncate text-sm rounded-lg px-3 py-1.5 border transition-colors
                    ${extraFile ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                                : "border-white/10 bg-white/[0.04] text-zinc-400 hover:border-white/20"}`}>
                  {extraFile ? extraFile.name : t("toolRun.chooseLogo")}
                </button>
              </div>
            )}

            <ToolFields fields={tool.fields} values={params} onChange={setParam} />

            {loading && uploadProgress > 0 && uploadProgress < 100 && (
              <div>
                <div className="flex justify-between text-xs text-zinc-500 mb-1.5">
                  <span>{t("newVideo.uploading")}</span><span>{uploadProgress}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-white/5 overflow-hidden">
                  <div className="h-full progress-pulse rounded-full" style={{ width: `${uploadProgress}%` }} />
                </div>
              </div>
            )}

            {(localError || error) && (
              <div className="rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
                {localError || error}
              </div>
            )}

            <Button type="submit" loading={loading} size="lg">{t("toolRun.run")}</Button>
          </form>
        </Card>
      )}
    </div>
  );
}
