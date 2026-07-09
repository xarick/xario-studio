import { useState, useRef } from "react";
import { useParams, Navigate, Link } from "react-router-dom";
import {
  Upload, Download, Loader2, RotateCcw, AlertCircle, ArrowLeft, Image as ImageIcon,
} from "lucide-react";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { ToolFields } from "../components/ToolFields";
import { getTool, defaultParams, ACCENTS } from "../config/tools";
import { useMediaJob, jobErrorText } from "../hooks/useMediaJob";
import { loadImageResult, downloadName } from "../utils/imageJob";
import { submitImageTool, getImage, getImageStreamUrl, downloadImageBlob } from "../api/images";
import { extractApiError } from "../utils/format";

const CHECKER = {
  backgroundImage:
    "linear-gradient(45deg,#2a2a35 25%,transparent 25%),linear-gradient(-45deg,#2a2a35 25%,transparent 25%),linear-gradient(45deg,transparent 75%,#2a2a35 75%),linear-gradient(-45deg,transparent 75%,#2a2a35 75%)",
  backgroundSize: "20px 20px",
  backgroundPosition: "0 0,0 10px,10px -10px,-10px 0",
};

function isImage(f) {
  return f && (f.type.startsWith("image/") || /\.(png|jpg|jpeg|webp|bmp)$/i.test(f.name));
}

export default function ImageToolPage() {
  const { t } = useTranslation();
  const { op } = useParams();
  const tool = getTool("image", op);

  const [file, setFile] = useState(null);
  const [params, setParams] = useState(() => (tool ? defaultParams(tool) : {}));
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState("");
  const [localError, setLocalError] = useState("");
  const { job, result, error: jobError, isProcessing, start, reset: resetJob } =
    useMediaJob(loadImageResult, getImage);
  const fileRef = useRef(null);

  if (!tool) return <Navigate to="/tools" replace />;

  const accent = ACCENTS[tool.accent] ?? ACCENTS.rose;
  const Icon = tool.icon;

  function pickFile(f) {
    if (isImage(f)) { setFile(f); setLocalError(""); }
    else toast.error(t("image.onlyImage"));
  }
  function setParam(k, v) { setParams(p => ({ ...p, [k]: v })); }

  async function handleSubmit(e) {
    e.preventDefault();
    setLocalError(""); setError("");
    if (!file) { setLocalError(t("image.errors.noFile")); return; }
    setLoading(true); setUploadProgress(0);
    try {
      const { data } = await submitImageTool(file, tool.op, params, setUploadProgress);
      start(data);
    } catch (err) {
      setError(extractApiError(err));
    } finally {
      setLoading(false);
    }
  }

  function reset() { resetJob(); setFile(null); setLocalError(""); setError(""); }

  async function download() {
    if (!result) return;
    // crop/resize/upscale/enhance keep the source format, so the extension comes
    // from the finished job rather than from the tool's params.
    await downloadImageBlob(result.id, downloadName(file?.name, tool.id, result));
  }

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

      {(job?.status === "completed" && result) ? (
        <Card>
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-emerald-400">{t("toolRun.done")}</span>
              <button onClick={reset} className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 transition-colors">
                <RotateCcw size={13} /> {t("toolRun.new")}
              </button>
            </div>
            <div className="rounded-xl overflow-hidden flex items-center justify-center p-2" style={CHECKER}>
              <img src={getImageStreamUrl(result.id)} alt="result" className="max-h-[360px] max-w-full object-contain" />
            </div>
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
            <p className="font-medium text-zinc-200">{t("toolRun.processing")} · {job.progress_percent ?? 0}%</p>
          </div>
        </Card>
      ) : (
        <Card>
          <form onSubmit={handleSubmit} className="flex flex-col gap-6">
            <div
              onDragOver={e => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={e => { e.preventDefault(); setDragOver(false); pickFile(e.dataTransfer.files[0]); }}
              onClick={() => fileRef.current?.click()}
              className={`flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed
                p-10 cursor-pointer transition-all duration-200
                ${dragOver ? "drag-over" : "border-white/10 hover:border-rose-500/30 hover:bg-rose-500/3"}
                ${file ? "border-emerald-500/30 bg-emerald-500/5" : ""}`}
            >
              <input ref={fileRef} type="file" accept="image/*" className="hidden"
                onChange={e => e.target.files[0] && pickFile(e.target.files[0])} />
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center
                ${file ? "bg-emerald-500/15" : `${accent.bg} border ${accent.border}`}`}>
                <ImageIcon size={22} className={file ? "text-emerald-400" : accent.text} />
              </div>
              {file ? (
                <div className="text-center">
                  <p className="font-medium text-zinc-200 text-sm">{file.name}</p>
                  <p className="text-xs text-zinc-500 mt-0.5">{(file.size/1024/1024).toFixed(1)} MB</p>
                </div>
              ) : (
                <div className="text-center">
                  <p className="text-sm text-zinc-400">{t("image.drop")}</p>
                  <p className="text-xs text-zinc-600 mt-1">{t("image.formats")}</p>
                </div>
              )}
            </div>

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
