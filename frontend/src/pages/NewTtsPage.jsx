import { useState, useRef } from "react";
import { Mic, Sparkles, Download, Loader2, RotateCcw, AlertCircle, Volume2, Upload, X } from "lucide-react";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { useVideo } from "../hooks/useVideo";
import { useMediaJob, jobErrorText } from "../hooks/useMediaJob";
import { LANGUAGES, VOICES, TTS_MAX_CHARS as MAX_CHARS } from "../config/audio";
import { getVideoShorts } from "../api/videos";
import { downloadShortBlob, getShortStreamUrl } from "../api/shorts";

function isAudio(f) {
  return f && (f.type.startsWith("audio/")
    || /\.(mp3|wav|m4a|aac|ogg|flac|opus)$/i.test(f.name));
}

/** A completed TTS job always has exactly one short — its absence is an error. */
async function loadSpeech(jobId) {
  const { data } = await getVideoShorts(jobId);
  const short = (data ?? [])[0];
  if (!short) throw new Error("no short");
  return short;
}

export default function NewTtsPage() {
  const { t } = useTranslation();
  const { submitSpeech, loading, uploadProgress, error } = useVideo();
  const { job, result: audio, error: jobError, isProcessing, start, reset: resetJob } =
    useMediaJob(loadSpeech);
  const [text, setText] = useState("");
  const [language, setLanguage] = useState("uz");
  const [voice, setVoice] = useState(VOICES[0]);
  const [refFile, setRefFile] = useState(null);
  const [localError, setLocalError] = useState("");
  const refInput = useRef(null);

  function pickRef(f) {
    if (f && isAudio(f)) { setRefFile(f); setLocalError(""); }
    else toast.error(t("tts.onlyAudio"));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLocalError("");
    if (!text.trim()) { setLocalError(t("tts.errors.noText")); return; }
    start(await submitSpeech(text.trim(), {
      language,
      voice: refFile ? "" : voice,
      referenceAudio: refFile,
    }));
  }

  function reset() { resetJob(); setLocalError(""); }

  async function download() {
    if (!audio) return;
    await downloadShortBlob(audio.id, `${t("tts.fileName")}.mp3`);
  }

  return (
    <div className="max-w-xl mx-auto flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">{t("tts.title")}</h1>
        <p className="text-zinc-500 mt-1 text-sm">{t("tts.subtitle")}</p>
      </div>

      {job?.status === "completed" && audio ? (
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between px-1">
            <span className="text-sm font-semibold text-emerald-400">{t("tts.done")}</span>
            <button onClick={reset} className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 transition-colors">
              <RotateCcw size={13} /> {t("tts.new")}
            </button>
          </div>
          <Card>
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-amber-500/12 border border-amber-500/20 flex items-center justify-center">
                  <Volume2 size={16} className="text-amber-400" />
                </div>
                <span className="font-semibold text-zinc-200">{t("tts.result")}</span>
              </div>
              <audio src={getShortStreamUrl(audio.id)} controls className="w-full" />
              <Button onClick={download} variant="secondary" size="sm">
                <Download size={15} /> {t("tts.download")}
              </Button>
            </div>
          </Card>
        </div>
      ) : (job?.status === "failed" || jobError) ? (
        <Card>
          <div className="flex flex-col items-center gap-4 py-10 text-center">
            <AlertCircle size={32} className="text-red-400" />
            <p className="text-sm text-zinc-400">{jobErrorText(t, job, jobError, "tts.failed")}</p>
            <Button size="sm" variant="secondary" onClick={reset}>{t("tts.new")}</Button>
          </div>
        </Card>
      ) : isProcessing ? (
        <Card>
          <div className="flex flex-col items-center gap-4 py-12 text-center">
            <Loader2 size={32} className="text-amber-400 animate-spin" />
            <div>
              <p className="font-medium text-zinc-200">{t("tts.processing")}</p>
              <p className="text-sm text-zinc-600 mt-1">{t("tts.processingHint")} · {job.progress_percent ?? 0}%</p>
            </div>
          </div>
        </Card>
      ) : (
        <Card>
          <form onSubmit={handleSubmit} className="flex flex-col gap-5">
            {/* Text */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-sm font-medium text-zinc-300">{t("tts.textLabel")}</label>
                <span className={`text-xs ${text.length > MAX_CHARS ? "text-red-400" : "text-zinc-600"}`}>
                  {text.length} / {MAX_CHARS}
                </span>
              </div>
              <textarea
                value={text}
                onChange={e => setText(e.target.value.slice(0, MAX_CHARS))}
                rows={6}
                placeholder={t("tts.textPlaceholder")}
                className="w-full rounded-xl bg-white/5 border border-white/10 px-4 py-3 text-sm text-zinc-200
                  placeholder:text-zinc-600 focus:outline-none focus:border-amber-500/40 resize-y"
              />
            </div>

            {/* Language + voice */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium text-zinc-300 mb-1.5 block">{t("tts.language")}</label>
                <select
                  value={language}
                  onChange={e => setLanguage(e.target.value)}
                  className="w-full rounded-xl bg-white/5 border border-white/10 px-3 py-2.5 text-sm text-zinc-200
                    focus:outline-none focus:border-amber-500/40"
                >
                  {LANGUAGES.map(l => (
                    <option key={l} value={l} className="bg-zinc-900">{t(`tts.lang.${l}`)}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium text-zinc-300 mb-1.5 block">{t("tts.voice")}</label>
                <select
                  value={voice}
                  onChange={e => setVoice(e.target.value)}
                  disabled={!!refFile}
                  className="w-full rounded-xl bg-white/5 border border-white/10 px-3 py-2.5 text-sm text-zinc-200
                    focus:outline-none focus:border-amber-500/40 disabled:opacity-40"
                >
                  {VOICES.map(v => (
                    <option key={v} value={v} className="bg-zinc-900">{v}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Optional voice cloning */}
            <div>
              <label className="text-sm font-medium text-zinc-300 mb-1.5 block">{t("tts.clone")}</label>
              {refFile ? (
                <div className="flex items-center gap-2 rounded-xl bg-amber-500/5 border border-amber-500/20 px-3 py-2.5">
                  <Mic size={15} className="text-amber-400 shrink-0" />
                  <span className="flex-1 text-sm text-zinc-300 truncate">{refFile.name}</span>
                  <button type="button" onClick={() => setRefFile(null)} className="text-zinc-500 hover:text-red-400">
                    <X size={15} />
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => refInput.current?.click()}
                  className="w-full flex items-center justify-center gap-2 rounded-xl border border-dashed border-white/10
                    px-3 py-2.5 text-sm text-zinc-500 hover:border-amber-500/30 hover:text-zinc-300 transition-colors"
                >
                  <Upload size={15} /> {t("tts.cloneHint")}
                </button>
              )}
              <input ref={refInput} type="file" accept="audio/*" className="hidden"
                onChange={e => e.target.files[0] && pickRef(e.target.files[0])} />
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

            <div className="flex items-start gap-2.5 rounded-xl bg-amber-500/5 border border-amber-500/15 px-4 py-3">
              <Sparkles size={14} className="text-amber-400 mt-0.5 shrink-0" />
              <p className="text-xs text-zinc-500">{t("tts.info")}</p>
            </div>

            {(localError || error) && (
              <div className="rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
                {localError || error}
              </div>
            )}

            <Button type="submit" loading={loading} size="lg">
              <Mic size={18} /> {t("tts.submit")}
            </Button>
          </form>
        </Card>
      )}
    </div>
  );
}
