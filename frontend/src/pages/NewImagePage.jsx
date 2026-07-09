import { useState, useRef } from "react";
import { ImagePlus, Upload, Image as ImageIcon, Download, Loader2, RotateCcw, AlertCircle, Scissors } from "lucide-react";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { useMediaJob, jobErrorText } from "../hooks/useMediaJob";
import { loadImageResult } from "../utils/imageJob";
import { extractApiError } from "../utils/format";
import { submitBgRemove, getImage, getImageStreamUrl, downloadImageBlob } from "../api/images";

// CSS checkerboard so transparency in the result is visible.
const CHECKER = {
  backgroundImage:
    "linear-gradient(45deg,#2a2a35 25%,transparent 25%),linear-gradient(-45deg,#2a2a35 25%,transparent 25%),linear-gradient(45deg,transparent 75%,#2a2a35 75%),linear-gradient(-45deg,transparent 75%,#2a2a35 75%)",
  backgroundSize: "20px 20px",
  backgroundPosition: "0 0,0 10px,10px -10px,-10px 0",
};

function isImage(f) {
  return f && (f.type.startsWith("image/") || /\.(png|jpg|jpeg|webp|bmp)$/i.test(f.name));
}

export default function NewImagePage() {
  const { t } = useTranslation();
  const { job, result, error: jobError, isProcessing, start, reset: resetJob } =
    useMediaJob(loadImageResult, getImage);
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState("");
  const [localError, setLocalError] = useState("");
  const fileRef = useRef(null);

  function pickFile(f) {
    if (f && isImage(f)) { setFile(f); setLocalError(""); }
    else toast.error(t("image.onlyImage"));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLocalError(""); setError("");
    if (!file) { setLocalError(t("image.errors.noFile")); return; }
    setLoading(true); setUploadProgress(0);
    try {
      const { data } = await submitBgRemove(file, setUploadProgress);
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
    const baseName = (file?.name || "image").replace(/\.[^.]+$/, "");
    await downloadImageBlob(result.id, `${baseName}_no-bg.png`);   // always PNG (alpha)
  }

  return (
    <div className="max-w-xl mx-auto flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">{t("image.title")}</h1>
        <p className="text-zinc-500 mt-1 text-sm">{t("image.subtitle")}</p>
      </div>

      {(job?.status === "completed" && result) ? (
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between px-1">
            <span className="text-sm font-semibold text-emerald-400">{t("image.done")}</span>
            <button onClick={reset} className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 transition-colors">
              <RotateCcw size={13} /> {t("image.new")}
            </button>
          </div>
          <Card>
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-rose-500/12 border border-rose-500/20 flex items-center justify-center">
                  <Scissors size={16} className="text-rose-400" />
                </div>
                <span className="font-semibold text-zinc-200">{t("image.result")}</span>
              </div>
              <div className="rounded-xl overflow-hidden flex items-center justify-center p-2" style={CHECKER}>
                <img src={getImageStreamUrl(result.id)} alt="result" className="max-h-[360px] max-w-full object-contain" />
              </div>
              <Button onClick={download} variant="secondary" size="sm">
                <Download size={15} /> {t("image.download")}
              </Button>
            </div>
          </Card>
        </div>
      ) : (job?.status === "failed" || jobError) ? (
        <Card>
          <div className="flex flex-col items-center gap-4 py-10 text-center">
            <AlertCircle size={32} className="text-red-400" />
            <p className="text-sm text-zinc-400">{jobErrorText(t, job, jobError, "image.failed")}</p>
            <Button size="sm" variant="secondary" onClick={reset}>{t("image.new")}</Button>
          </div>
        </Card>
      ) : isProcessing ? (
        <Card>
          <div className="flex flex-col items-center gap-4 py-12 text-center">
            <Loader2 size={32} className="text-rose-400 animate-spin" />
            <div>
              <p className="font-medium text-zinc-200">{t("image.processing")}</p>
              <p className="text-sm text-zinc-600 mt-1">{t("image.processingHint")} · {job.progress_percent ?? 0}%</p>
            </div>
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
                ${file ? "bg-emerald-500/15" : "bg-rose-500/10 border border-rose-500/20"}`}>
                {file ? <ImageIcon size={22} className="text-emerald-400" /> : <Upload size={22} className="text-rose-400" />}
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

            <div className="flex items-start gap-2.5 rounded-xl bg-rose-500/5 border border-rose-500/15 px-4 py-3">
              <Scissors size={14} className="text-rose-400 mt-0.5 shrink-0" />
              <p className="text-xs text-zinc-500">{t("image.info")}</p>
            </div>

            {(localError || error) && (
              <div className="rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
                {localError || error}
              </div>
            )}

            <Button type="submit" loading={loading} size="lg">
              <ImagePlus size={18} /> {t("image.submit")}
            </Button>
          </form>
        </Card>
      )}
    </div>
  );
}
