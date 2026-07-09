import { useState, useRef } from "react";
import { Mic2, Music, Upload, FileAudio, Download, Loader2, RotateCcw, AlertCircle, Video } from "lucide-react";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { useVideo } from "../hooks/useVideo";
import { useMediaKind } from "../hooks/useMediaKind";
import { useMediaJob, jobErrorText } from "../hooks/useMediaJob";
import { getVideoShorts } from "../api/videos";
import { downloadShortBlob, getShortStreamUrl } from "../api/shorts";

// index → stem metadata (backend order: 1=vocals, 2=instrumental, 3=karaoke)
const STEMS = {
  1: { key: "vocals",       icon: Mic2,  ext: "mp3", video: false },
  2: { key: "instrumental", icon: Music, ext: "mp3", video: false },
  3: { key: "karaoke",      icon: Video, ext: "mp4", video: true },
};

/** Separation always yields at least vocals + instrumental. */
async function loadStems(jobId) {
  const { data } = await getVideoShorts(jobId);
  const stems = (data ?? [])
    .map(s => ({ short: s, meta: STEMS[s.index_number] }))
    .filter(x => x.meta);
  if (!stems.length) throw new Error("no stems");
  return stems;
}

export default function NewSeparatePage() {
  const { t } = useTranslation();
  const { isAudio, accept, isAllowed } = useMediaKind();
  const { submitSeparate, loading, uploadProgress, error } = useVideo();
  const { job, result, error: jobError, isProcessing, start, reset: resetJob } =
    useMediaJob(loadStems);
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [localError, setLocalError] = useState("");
  const fileRef = useRef(null);

  const stems = result ?? [];

  function pickFile(f) {
    if (isAllowed(f)) { setFile(f); setLocalError(""); }
    else toast.error(t(isAudio ? "media.onlyAudio" : "media.onlyVideo"));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLocalError("");
    if (!file) { setLocalError(t("newVideo.errors.noFile")); return; }
    start(await submitSeparate(file));
  }

  function reset() { resetJob(); setFile(null); setLocalError(""); }

  async function download(short, meta) {
    const baseName = (file?.name || "audio").replace(/\.[^.]+$/, "");
    await downloadShortBlob(short.id, `${baseName}_${t(`separate.${meta.key}`)}.${meta.ext}`);
  }

  return (
    <div className="max-w-xl mx-auto flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">{t("separate.title")}</h1>
        <p className="text-zinc-500 mt-1 text-sm">{t("separate.subtitle")}</p>
      </div>

      {job?.status === "completed" && stems.length ? (
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between px-1">
            <span className="text-sm font-semibold text-emerald-400">{t("separate.done")}</span>
            <button onClick={reset} className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 transition-colors">
              <RotateCcw size={13} /> {t("separate.new")}
            </button>
          </div>
          {stems.map(({ short, meta }) => {
            const Icon = meta.icon;
            return (
              <Card key={short.id}>
                <div className="flex flex-col gap-3">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-violet-500/12 border border-violet-500/20 flex items-center justify-center">
                      <Icon size={16} className="text-violet-400" />
                    </div>
                    <span className="font-semibold text-zinc-200">{t(`separate.${meta.key}`)}</span>
                  </div>
                  {meta.video
                    ? <video src={getShortStreamUrl(short.id)} controls className="w-full rounded-xl bg-black max-h-[320px]" />
                    : <audio src={getShortStreamUrl(short.id)} controls className="w-full" />}
                  <Button onClick={() => download(short, meta)} variant="secondary" size="sm">
                    <Download size={15} /> {t("separate.download")}
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      ) : (job?.status === "failed" || jobError) ? (
        <Card>
          <div className="flex flex-col items-center gap-4 py-10 text-center">
            <AlertCircle size={32} className="text-red-400" />
            <p className="text-sm text-zinc-400">{jobErrorText(t, job, jobError, "separate.failed")}</p>
            <Button size="sm" variant="secondary" onClick={reset}>{t("separate.new")}</Button>
          </div>
        </Card>
      ) : isProcessing ? (
        <Card>
          <div className="flex flex-col items-center gap-4 py-12 text-center">
            <Loader2 size={32} className="text-violet-400 animate-spin" />
            <div>
              <p className="font-medium text-zinc-200">{t("separate.processing")}</p>
              <p className="text-sm text-zinc-600 mt-1">{t("separate.processingHint")} · {job.progress_percent ?? 0}%</p>
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
              <Music size={14} className="text-blue-400 mt-0.5 shrink-0" />
              <p className="text-xs text-zinc-500">{t("separate.info")}</p>
            </div>

            {(localError || error) && (
              <div className="rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
                {localError || error}
              </div>
            )}

            <Button type="submit" loading={loading} size="lg">
              <Mic2 size={18} /> {t("separate.submit")}
            </Button>
          </form>
        </Card>
      )}
    </div>
  );
}
