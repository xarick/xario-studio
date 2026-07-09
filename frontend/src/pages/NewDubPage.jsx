import { useState, useRef } from "react";
import { Languages, Upload, FileAudio, Video, Download, Loader2, RotateCcw, AlertCircle } from "lucide-react";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { useVideo } from "../hooks/useVideo";
import { useMediaKind } from "../hooks/useMediaKind";
import { useMediaJob, jobErrorText } from "../hooks/useMediaJob";
import { LANGUAGES, VOICES } from "../config/audio";
import { getVideoShorts } from "../api/videos";
import { downloadShortBlob, getShortStreamUrl } from "../api/shorts";

/** A completed dub job always has exactly one short — its absence is an error. */
async function loadDubbed(jobId) {
  const { data } = await getVideoShorts(jobId);
  const short = (data ?? [])[0];
  if (!short) throw new Error("no short");
  return short;
}

export default function NewDubPage() {
  const { t } = useTranslation();
  const { isAudio, accept, isAllowed } = useMediaKind();
  const { submitDubbing, loading, uploadProgress, error } = useVideo();
  const { job, result, error: jobError, isProcessing, start, reset: resetJob } =
    useMediaJob(loadDubbed);
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [sourceLang, setSourceLang] = useState("");
  const [targetLang, setTargetLang] = useState("ru");
  const [cloneVoice, setCloneVoice] = useState(true);
  const [voice, setVoice] = useState(VOICES[0]);
  const [localError, setLocalError] = useState("");
  const fileRef = useRef(null);

  const isVideo = file && (file.type.startsWith("video/") || /\.(mp4|mov|avi|mkv|webm|m4v)$/i.test(file.name));

  function pickFile(f) {
    if (isAllowed(f)) { setFile(f); setLocalError(""); }
    else toast.error(t(isAudio ? "media.onlyAudio" : "media.onlyVideo"));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLocalError("");
    if (!file) { setLocalError(t("newVideo.errors.noFile")); return; }
    start(await submitDubbing(file, {
      targetLanguage: targetLang,
      sourceLanguage: sourceLang,
      voice: cloneVoice ? "" : voice,
    }));
  }

  function reset() { resetJob(); setFile(null); setLocalError(""); }

  async function download() {
    if (!result) return;
    const baseName = (file?.name || "dub").replace(/\.[^.]+$/, "");
    const ext = isVideo ? "mp4" : "mp3";
    await downloadShortBlob(result.id, `${baseName}_${targetLang}.${ext}`);
  }

  return (
    <div className="max-w-xl mx-auto flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">{t("dub.title")}</h1>
        <p className="text-zinc-500 mt-1 text-sm">{t("dub.subtitle")}</p>
      </div>

      {job?.status === "completed" && result ? (
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between px-1">
            <span className="text-sm font-semibold text-emerald-400">{t("dub.done")}</span>
            <button onClick={reset} className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 transition-colors">
              <RotateCcw size={13} /> {t("dub.new")}
            </button>
          </div>
          <Card>
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-violet-500/12 border border-violet-500/20 flex items-center justify-center">
                  <Languages size={16} className="text-violet-400" />
                </div>
                <span className="font-semibold text-zinc-200">{t("dub.result")} · {t(`tts.lang.${targetLang}`)}</span>
              </div>
              {isVideo
                ? <video src={getShortStreamUrl(result.id)} controls className="w-full rounded-xl bg-black max-h-[360px]" />
                : <audio src={getShortStreamUrl(result.id)} controls className="w-full" />}
              <Button onClick={download} variant="secondary" size="sm">
                <Download size={15} /> {t("dub.download")}
              </Button>
            </div>
          </Card>
        </div>
      ) : (job?.status === "failed" || jobError) ? (
        <Card>
          <div className="flex flex-col items-center gap-4 py-10 text-center">
            <AlertCircle size={32} className="text-red-400" />
            <p className="text-sm text-zinc-400">{jobErrorText(t, job, jobError, "dub.failed")}</p>
            <Button size="sm" variant="secondary" onClick={reset}>{t("dub.new")}</Button>
          </div>
        </Card>
      ) : isProcessing ? (
        <Card>
          <div className="flex flex-col items-center gap-4 py-12 text-center">
            <Loader2 size={32} className="text-violet-400 animate-spin" />
            <div>
              <p className="font-medium text-zinc-200">{t("dub.processing")}</p>
              <p className="text-sm text-zinc-600 mt-1">{t("dub.processingHint")} · {job.progress_percent ?? 0}%</p>
            </div>
          </div>
        </Card>
      ) : (
        <Card>
          <form onSubmit={handleSubmit} className="flex flex-col gap-5">
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
                {file ? (isVideo ? <Video size={22} className="text-emerald-400" /> : <FileAudio size={22} className="text-emerald-400" />)
                      : <Upload size={22} className="text-violet-400" />}
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

            {/* Source → target language */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium text-zinc-300 mb-1.5 block">{t("dub.sourceLang")}</label>
                <select
                  value={sourceLang}
                  onChange={e => setSourceLang(e.target.value)}
                  className="w-full rounded-xl bg-white/5 border border-white/10 px-3 py-2.5 text-sm text-zinc-200
                    focus:outline-none focus:border-violet-500/40"
                >
                  <option value="" className="bg-zinc-900">{t("newVideo.langAuto")}</option>
                  {LANGUAGES.map(l => (
                    <option key={l} value={l} className="bg-zinc-900">{t(`tts.lang.${l}`)}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium text-zinc-300 mb-1.5 block">{t("dub.targetLang")}</label>
                <select
                  value={targetLang}
                  onChange={e => setTargetLang(e.target.value)}
                  className="w-full rounded-xl bg-white/5 border border-white/10 px-3 py-2.5 text-sm text-zinc-200
                    focus:outline-none focus:border-violet-500/40"
                >
                  {LANGUAGES.map(l => (
                    <option key={l} value={l} className="bg-zinc-900">{t(`tts.lang.${l}`)}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Voice */}
            <div>
              <label className="flex items-center gap-2.5 cursor-pointer">
                <input type="checkbox" checked={cloneVoice} onChange={e => setCloneVoice(e.target.checked)}
                  className="w-4 h-4 accent-violet-500" />
                <span className="text-sm text-zinc-300">{t("dub.cloneVoice")}</span>
              </label>
              {!cloneVoice && (
                <select
                  value={voice}
                  onChange={e => setVoice(e.target.value)}
                  className="mt-2 w-full rounded-xl bg-white/5 border border-white/10 px-3 py-2.5 text-sm text-zinc-200
                    focus:outline-none focus:border-violet-500/40"
                >
                  {VOICES.map(v => (
                    <option key={v} value={v} className="bg-zinc-900">{v}</option>
                  ))}
                </select>
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
              <Languages size={14} className="text-blue-400 mt-0.5 shrink-0" />
              <p className="text-xs text-zinc-500">{t("dub.info")}</p>
            </div>

            {(localError || error) && (
              <div className="rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
                {localError || error}
              </div>
            )}

            <Button type="submit" loading={loading} size="lg">
              <Languages size={18} /> {t("dub.submit")}
            </Button>
          </form>
        </Card>
      )}
    </div>
  );
}
