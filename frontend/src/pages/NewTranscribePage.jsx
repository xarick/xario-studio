import { useState, useRef } from "react";
import { FileAudio, FileVideo, Upload, FileText, Download, Loader2, RotateCcw, AlertCircle } from "lucide-react";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { useVideo } from "../hooks/useVideo";
import { useMediaJob, jobErrorText } from "../hooks/useMediaJob";
import { getTranscript } from "../api/videos";
import { toTxt, toPlain, toSrt, toVtt, downloadText } from "../utils/transcript";

const SUB_LANGS = [
  { id: "",   label: "Auto" },
  { id: "uz", label: "O‘zbekcha" },
  { id: "ru", label: "Русский" },
  { id: "en", label: "English" },
  { id: "tr", label: "Türkçe" },
];

// The backend transcribes both audio and video (it decodes the audio track),
// so we accept either here — "video to text" works the same way.
function isMedia(f) {
  return f && (f.type.startsWith("audio/") || f.type.startsWith("video/")
    || /\.(mp3|wav|m4a|aac|ogg|flac|opus|mp4|mov|avi|mkv|webm|m4v)$/i.test(f.name));
}
function isVideo(f) {
  return f && (f.type.startsWith("video/") || /\.(mp4|mov|avi|mkv|webm|m4v)$/i.test(f.name));
}

/** The backend fails the job when no speech is detected, so a completed job
 *  without text means the transcript could not be fetched. */
async function loadTranscript(jobId) {
  const { data } = await getTranscript(jobId);
  if (!data?.text && !(data?.segments ?? []).length) throw new Error("empty transcript");
  return data;
}

export default function NewTranscribePage() {
  const { t } = useTranslation();
  const { submitTranscribe, loading, uploadProgress, error } = useVideo();
  const { job, result: transcript, error: jobError, isProcessing, start, reset: resetJob } =
    useMediaJob(loadTranscript);
  const [file, setFile] = useState(null);
  const [lang, setLang] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [localError, setLocalError] = useState("");
  const fileRef = useRef(null);

  function pickFile(f) {
    if (f && isMedia(f)) { setFile(f); setLocalError(""); }
    else toast.error(t("transcribe.onlyMedia"));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLocalError("");
    if (!file) { setLocalError(t("newVideo.errors.noFile")); return; }
    start(await submitTranscribe(file, lang));
  }

  function reset() { resetJob(); setFile(null); setLocalError(""); }

  const base = (file?.name || "transcript").replace(/\.[^.]+$/, "");
  const segs = transcript?.segments ?? [];

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">{t("transcribe.title")}</h1>
        <p className="text-zinc-500 mt-1 text-sm">{t("transcribe.subtitle")}</p>
      </div>

      {/* ── Result ─────────────────────────────────────────── */}
      {job?.status === "completed" && transcript ? (
        <Card>
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText size={18} className="text-emerald-400" />
                <span className="font-semibold text-zinc-200">{t("transcribe.done")}</span>
                <span className="text-xs text-zinc-600">· {segs.length} {t("transcribe.segments")}</span>
              </div>
              <button onClick={reset} className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 transition-colors">
                <RotateCcw size={13} /> {t("transcribe.new")}
              </button>
            </div>

            {/* Download buttons */}
            <div className="flex flex-wrap gap-2">
              {[
                { label: "TXT", fn: () => downloadText(`${base}.txt`, toTxt(segs)) },
                { label: t("transcribe.plain"), fn: () => downloadText(`${base}.txt`, toPlain(segs)) },
                { label: "SRT", fn: () => downloadText(`${base}.srt`, toSrt(segs)) },
                { label: "VTT", fn: () => downloadText(`${base}.vtt`, toVtt(segs)) },
              ].map(b => (
                <button key={b.label} onClick={b.fn}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium border border-violet-500/25 bg-violet-500/10 text-violet-300 hover:bg-violet-500/15 transition-all">
                  <Download size={13} /> {b.label}
                </button>
              ))}
            </div>

            {/* Preview */}
            <div className="rounded-xl bg-black/20 border border-white/[0.06] max-h-[420px] overflow-y-auto p-1">
              {segs.map((s, i) => (
                <div key={i} className="flex gap-3 px-3 py-1.5 hover:bg-white/[0.02] rounded-lg">
                  <span className="text-[11px] text-violet-400/70 tabular-nums shrink-0 pt-0.5 w-16">
                    {new Date(s.start * 1000).toISOString().substr(11, 8)}
                  </span>
                  <span className="text-sm text-zinc-300 leading-relaxed">{s.text}</span>
                </div>
              ))}
            </div>
          </div>
        </Card>
      ) : (job?.status === "failed" || jobError) ? (
        <Card>
          <div className="flex flex-col items-center gap-4 py-10 text-center">
            <AlertCircle size={32} className="text-red-400" />
            <p className="text-sm text-zinc-400">{jobErrorText(t, job, jobError, "transcribe.failed")}</p>
            <Button size="sm" variant="secondary" onClick={reset}>{t("transcribe.new")}</Button>
          </div>
        </Card>
      ) : isProcessing ? (
        <Card>
          <div className="flex flex-col items-center gap-4 py-12 text-center">
            <Loader2 size={32} className="text-violet-400 animate-spin" />
            <div>
              <p className="font-medium text-zinc-200">{t("transcribe.processing")}</p>
              <p className="text-sm text-zinc-600 mt-1">{t("transcribe.processingHint")} · {job.progress_percent ?? 0}%</p>
            </div>
          </div>
        </Card>
      ) : (
        /* ── Upload form ──────────────────────────────────── */
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
              <input ref={fileRef} type="file" accept="audio/*,video/*" className="hidden"
                onChange={e => e.target.files[0] && pickFile(e.target.files[0])} />
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center
                ${file ? "bg-emerald-500/15" : "bg-violet-500/10 border border-violet-500/20"}`}>
                {file
                  ? (isVideo(file) ? <FileVideo size={22} className="text-emerald-400" /> : <FileAudio size={22} className="text-emerald-400" />)
                  : <Upload size={22} className="text-violet-400" />}
              </div>
              {file ? (
                <div className="text-center">
                  <p className="font-medium text-zinc-200 text-sm">{file.name}</p>
                  <p className="text-xs text-zinc-500 mt-0.5">{(file.size/1024/1024).toFixed(1)} MB</p>
                </div>
              ) : (
                <div className="text-center">
                  <p className="text-sm text-zinc-400">{t("transcribe.drop")}</p>
                  <p className="text-xs text-zinc-600 mt-1">{t("transcribe.formats")}</p>
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

            <div className="flex items-center justify-between gap-4 px-4 py-3 rounded-xl bg-white/[0.02] border border-white/[0.05]">
              <label htmlFor="lang" className="text-sm font-medium text-zinc-300">{t("newVideo.subtitleLang")}</label>
              <select id="lang" value={lang} onChange={e => setLang(e.target.value)}
                className="text-sm bg-zinc-800/80 border border-white/10 rounded-lg px-3 py-1.5 text-zinc-200 focus:outline-none focus:border-violet-500/50 cursor-pointer">
                {SUB_LANGS.map(l => <option key={l.id} value={l.id}>{l.label}</option>)}
              </select>
            </div>

            {(localError || error) && (
              <div className="rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
                {localError || error}
              </div>
            )}

            <Button type="submit" loading={loading} size="lg">
              <FileText size={18} /> {t("transcribe.submit")}
            </Button>
          </form>
        </Card>
      )}
    </div>
  );
}
