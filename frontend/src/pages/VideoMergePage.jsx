import { useState, useRef } from "react";
import { Link } from "react-router-dom";
import {
  Download, Loader2, RotateCcw, AlertCircle, ArrowLeft,
  FileVideo, X, Plus, ChevronUp, ChevronDown, Film, Wand2, Music,
} from "lucide-react";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { mergeVideos, getVideoShorts } from "../api/videos";
import { useMediaJob, jobErrorText } from "../hooks/useMediaJob";
import { downloadShortBlob, getShortStreamUrl } from "../api/shorts";
import { isVideoFile } from "../utils/validators";
import { extractApiError } from "../utils/format";

// Transition ids must match tools.VIDEO_TRANSITIONS on the backend.
const TRANSITIONS = [
  "none", "fade", "fadeblack", "fadewhite", "dissolve", "wave",
  "wipeleft", "wiperight", "slideleft", "slideright", "slideup", "slidedown",
  "circleopen", "radial", "smoothleft", "pixelize",
];

const ASPECTS = ["9:16", "1:1", "16:9", "original"];


/** A completed job always has exactly one short — its absence is an error. */
async function loadShort(jobId) {
  const { data } = await getVideoShorts(jobId);
  const short = (data ?? [])[0];
  if (!short) throw new Error("no short");
  return short;
}

export default function VideoMergePage() {
  const { t } = useTranslation();

  const [files, setFiles] = useState([]);          // ordered list
  const [transition, setTransition] = useState("fade");
  const [duration, setDuration] = useState(1.0);
  const [aspect, setAspect] = useState("9:16");
  const [music, setMusic] = useState(null);          // optional background track
  const [musicVolume, setMusicVolume] = useState(0.5);
  const [loading, setLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState("");
  const [localError, setLocalError] = useState("");
  const { job, result, error: jobError, isProcessing, start, reset: resetJob } =
    useMediaJob(loadShort);
  const addRef = useRef(null);
  const musicRef = useRef(null);

  const AUDIO_RE = /\.(mp3|wav|m4a|aac|ogg|flac|opus)$/i;


  function addFiles(list) {
    const valid = Array.from(list).filter(isVideoFile);
    if (!valid.length) { toast.error(t("media.onlyVideo")); return; }
    setFiles(f => [...f, ...valid]); setLocalError("");
  }
  function removeAt(i) {
    setFiles(list => list.filter((_, j) => j !== i));
  }
  function move(i, dir) {
    setFiles(list => {
      const j = i + dir;
      if (j < 0 || j >= list.length) return list;
      const next = [...list];
      [next[i], next[j]] = [next[j], next[i]];
      return next;
    });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLocalError(""); setError("");
    if (files.length < 2) { setLocalError(t("videoMerge.needTwo")); return; }
    setLoading(true); setUploadProgress(0);
    try {
      const { data } = await mergeVideos(
        files,
        { transition, duration, aspect, music_volume: musicVolume },
        setUploadProgress,
        music,
      );
      start(data);
    } catch (err) {
      setError(extractApiError(err));
    } finally {
      setLoading(false);
    }
  }

  function pickMusic(f) {
    if (f && (f.type.startsWith("audio/") || AUDIO_RE.test(f.name))) {
      setMusic(f); setLocalError("");
    } else {
      toast.error(t("media.onlyAudio"));
    }
  }

  function reset() {
    resetJob(); setFiles([]); setMusic(null);
    setLocalError(""); setError("");
  }
  async function download() {
    if (!result) return;
    await downloadShortBlob(result.id, "merged.mp4");
  }


  return (
    <div className="max-w-xl mx-auto flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-start gap-3">
        <Link to="/tools" className="mt-1 text-zinc-600 hover:text-zinc-300 transition-colors"><ArrowLeft size={18} /></Link>
        <div className="w-11 h-11 rounded-xl bg-violet-500/12 border border-violet-500/20 flex items-center justify-center shrink-0">
          <Film size={20} className="text-violet-400" strokeWidth={1.8} />
        </div>
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-2xl font-bold text-zinc-100">{t("videoMerge.title")}</h1>
            <span className="text-[10px] bg-violet-500/12 text-violet-400 border border-violet-500/20 px-2 py-0.5 rounded-full font-semibold uppercase tracking-wide">
              {t("videoMerge.badge")}
            </span>
          </div>
          <p className="text-zinc-500 mt-1 text-sm">{t("videoMerge.subtitle")}</p>
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
            <video src={getShortStreamUrl(result.id)} controls className="w-full rounded-xl bg-black" />
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
            <Loader2 size={32} className="text-violet-400 animate-spin" />
            <p className="font-medium text-zinc-200">{t("toolRun.processing")} · {job.progress_percent ?? 0}%</p>
          </div>
        </Card>
      ) : (
        <Card>
          <form onSubmit={handleSubmit} className="flex flex-col gap-6">
            {/* ── Clip list ─────────────────────────────────────── */}
            <div className="flex flex-col gap-3">
              <input ref={addRef} type="file" accept="video/*" multiple className="hidden"
                onChange={e => { addFiles(e.target.files); e.target.value = ""; }} />
              {files.length > 0 && (
                <div className="flex flex-col gap-2">
                  {files.map((f, i) => (
                    <div key={i} className="flex items-center gap-2.5 rounded-xl bg-white/[0.03] border border-white/[0.07] px-3 py-2">
                      <span className="w-5 h-5 rounded-md bg-violet-500/15 text-violet-300 text-[11px] font-bold flex items-center justify-center shrink-0">{i + 1}</span>
                      <FileVideo size={15} className="text-zinc-500 shrink-0" />
                      <span className="text-sm text-zinc-300 truncate flex-1">{f.name}</span>
                      <div className="flex items-center gap-0.5">
                        <button type="button" onClick={() => move(i, -1)} disabled={i === 0}
                          className="text-zinc-600 hover:text-zinc-200 disabled:opacity-30 disabled:hover:text-zinc-600 transition-colors"><ChevronUp size={15} /></button>
                        <button type="button" onClick={() => move(i, 1)} disabled={i === files.length - 1}
                          className="text-zinc-600 hover:text-zinc-200 disabled:opacity-30 disabled:hover:text-zinc-600 transition-colors"><ChevronDown size={15} /></button>
                        <button type="button" onClick={() => removeAt(i)}
                          className="ml-1 text-zinc-600 hover:text-red-400 transition-colors"><X size={14} /></button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              <button type="button" onClick={() => addRef.current?.click()}
                className="flex items-center justify-center gap-2 rounded-xl border-2 border-dashed border-white/10
                  hover:border-violet-500/30 hover:bg-violet-500/3 py-4 text-sm text-zinc-400 transition-all">
                <Plus size={16} /> {t("videoMerge.addVideo")}
              </button>
              <p className="text-[11px] text-zinc-600">{t("videoMerge.concatHint")}</p>
            </div>

            {/* ── Transition ────────────────────────────────────── */}
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-zinc-300">{t("videoMerge.transition")}</label>
              <div className="grid grid-cols-2 gap-2">
                {TRANSITIONS.map(id => {
                  const active = transition === id;
                  return (
                    <button key={id} type="button" onClick={() => setTransition(id)}
                      className={`py-2 px-3 rounded-xl text-xs font-medium border text-left transition-all
                        ${active ? "border-violet-500/40 bg-violet-500/10 text-violet-300"
                                 : "border-white/8 bg-white/[0.02] text-zinc-400 hover:border-white/15"}`}>
                      {t(`videoMerge.transitions.${id}`)}
                    </button>
                  );
                })}
              </div>
              <p className="text-[11px] text-zinc-600">{t("videoMerge.transitionHint")}</p>
            </div>

            {/* ── Animation duration (hidden for hard cut) ──────── */}
            {transition !== "none" && (
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium text-zinc-300">{t("videoMerge.duration")}</label>
                  <span className="text-sm tabular-nums text-violet-300">{duration.toFixed(1)}s</span>
                </div>
                <input type="range" min={0.3} max={3} step={0.1} value={duration}
                  onChange={e => setDuration(Number(e.target.value))}
                  className="w-full accent-violet-500 cursor-pointer" />
              </div>
            )}

            {/* ── Aspect ────────────────────────────────────────── */}
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-zinc-300">{t("videoMerge.aspect")}</label>
              <div className="grid grid-cols-4 gap-2">
                {ASPECTS.map(id => {
                  const active = aspect === id;
                  return (
                    <button key={id} type="button" onClick={() => setAspect(id)}
                      className={`py-2 rounded-xl text-xs font-medium border transition-all
                        ${active ? "border-violet-500/40 bg-violet-500/10 text-violet-300"
                                 : "border-white/8 bg-white/[0.02] text-zinc-500 hover:border-white/15"}`}>
                      {id === "original" ? t("videoMerge.aspectOriginal") : id}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* ── Background music (optional) ───────────────────── */}
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-zinc-300 flex items-center gap-1.5">
                <Music size={14} className="text-violet-400" /> {t("videoMerge.music")}
              </label>
              <input ref={musicRef} type="file" accept="audio/*" className="hidden"
                onChange={e => e.target.files[0] && pickMusic(e.target.files[0])} />
              <div className="flex items-center gap-2">
                <button type="button" onClick={() => musicRef.current?.click()}
                  className={`flex-1 text-left text-sm rounded-xl px-3.5 py-2.5 border transition-colors truncate
                    ${music ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300" : "border-white/10 bg-white/[0.04] text-zinc-500 hover:border-white/20"}`}>
                  {music ? music.name : t("videoMerge.chooseMusic")}
                </button>
                {music && (
                  <button type="button" onClick={() => setMusic(null)}
                    className="text-zinc-600 hover:text-red-400 transition-colors"><X size={16} /></button>
                )}
              </div>
              {music && (
                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] text-zinc-500">{t("videoMerge.musicVolume")}</span>
                    <span className="text-xs tabular-nums text-violet-300">{Math.round(musicVolume * 100)}%</span>
                  </div>
                  <input type="range" min={0} max={1} step={0.05} value={musicVolume}
                    onChange={e => setMusicVolume(Number(e.target.value))}
                    className="w-full accent-violet-500 cursor-pointer" />
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

            {(localError || error) && (
              <div className="rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
                {localError || error}
              </div>
            )}

            <Button type="submit" loading={loading} size="lg"><Wand2 size={18} /> {t("toolRun.run")}</Button>
          </form>
        </Card>
      )}
    </div>
  );
}
