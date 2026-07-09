import { useState, useRef } from "react";
import { Wand2, Upload, FileAudio, Download, Loader2, RotateCcw, AlertCircle, Volume2 } from "lucide-react";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { useVideo } from "../hooks/useVideo";
import { useMediaKind } from "../hooks/useMediaKind";
import { useMediaJob, jobErrorText } from "../hooks/useMediaJob";
import { getVideoShorts } from "../api/videos";
import { downloadShortBlob, getShortStreamUrl } from "../api/shorts";

/** A completed cleanup job always has exactly one short. */
async function loadCleaned(jobId) {
  const { data } = await getVideoShorts(jobId);
  const short = (data ?? [])[0];
  if (!short) throw new Error("no short");
  return short;
}

export default function NewCleanupPage() {
  const { t } = useTranslation();
  const { isAudio, accept, isAllowed } = useMediaKind();
  const { submitCleanup, loading, uploadProgress, error } = useVideo();
  const { job, result, error: jobError, isProcessing, start, reset: resetJob } =
    useMediaJob(loadCleaned);
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [localError, setLocalError] = useState("");
  const fileRef = useRef(null);

  function pickFile(f) {
    if (isAllowed(f)) { setFile(f); setLocalError(""); }
    else toast.error(t(isAudio ? "media.onlyAudio" : "media.onlyVideo"));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLocalError("");
    if (!file) { setLocalError(t("newVideo.errors.noFile")); return; }
    start(await submitCleanup(file));
  }

  function reset() { resetJob(); setFile(null); setLocalError(""); }

  async function download() {
    if (!result) return;
    const isVideo = (result.file_path || "").endsWith(".mp4");
    const base = (file?.name || "cleaned").replace(/\.[^.]+$/, "");
    await downloadShortBlob(result.id, `${base}_cleaned.${isVideo ? "mp4" : "mp3"}`);
  }

  const resultIsVideo = (result?.file_path || "").endsWith(".mp4");

  return (
    <div className="max-w-xl mx-auto flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">{t("cleanup.title")}</h1>
        <p className="text-zinc-500 mt-1 text-sm">{t("cleanup.subtitle")}</p>
      </div>

      {job?.status === "completed" && result ? (
        <Card>
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Volume2 size={18} className="text-emerald-400" />
                <span className="font-semibold text-zinc-200">{t("cleanup.done")}</span>
              </div>
              <button onClick={reset} className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 transition-colors">
                <RotateCcw size={13} /> {t("cleanup.new")}
              </button>
            </div>

            {resultIsVideo ? (
              <video src={getShortStreamUrl(result.id)} controls className="w-full rounded-xl bg-black max-h-[360px]" />
            ) : (
              <audio src={getShortStreamUrl(result.id)} controls className="w-full" />
            )}

            <Button onClick={download} size="lg">
              <Download size={18} /> {t("cleanup.download")}
            </Button>
          </div>
        </Card>
      ) : (job?.status === "failed" || jobError) ? (
        <Card>
          <div className="flex flex-col items-center gap-4 py-10 text-center">
            <AlertCircle size={32} className="text-red-400" />
            <p className="text-sm text-zinc-400">{jobErrorText(t, job, jobError, "cleanup.failed")}</p>
            <Button size="sm" variant="secondary" onClick={reset}>{t("cleanup.new")}</Button>
          </div>
        </Card>
      ) : isProcessing ? (
        <Card>
          <div className="flex flex-col items-center gap-4 py-12 text-center">
            <Loader2 size={32} className="text-violet-400 animate-spin" />
            <div>
              <p className="font-medium text-zinc-200">{t("cleanup.processing")}</p>
              <p className="text-sm text-zinc-600 mt-1">{t("cleanup.processingHint")} · {job.progress_percent ?? 0}%</p>
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
                ${dragOver ? "drag-over" : "border-white/10 hover:border-violet-500/30 hover:bg-violet-500/3"}
                ${file ? "border-emerald-500/30 bg-emerald-500/5" : ""}`}
            >
              <input ref={fileRef} type="file" accept={accept} className="hidden"
                onChange={e => e.target.files[0] && pickFile(e.target.files[0])} />
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center
                ${file ? "bg-emerald-500/15" : "bg-violet-500/10 border border-violet-500/20"}`}>
                {file ? <FileAudio size={22} className="text-emerald-400" /> : <Upload size={22} className="text-violet-400" />}
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

            <div className="flex items-start gap-2.5 rounded-xl bg-blue-500/5 border border-blue-500/15 px-4 py-3">
              <Wand2 size={14} className="text-blue-400 mt-0.5 shrink-0" />
              <p className="text-xs text-zinc-500">{t("cleanup.info")}</p>
            </div>

            {(localError || error) && (
              <div className="rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
                {localError || error}
              </div>
            )}

            <Button type="submit" loading={loading} size="lg">
              <Wand2 size={18} /> {t("cleanup.submit")}
            </Button>
          </form>
        </Card>
      )}
    </div>
  );
}
