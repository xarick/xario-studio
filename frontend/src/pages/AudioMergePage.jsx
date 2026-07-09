import { useState, useRef } from "react";
import { useParams, Navigate, Link } from "react-router-dom";
import {
  Upload, Download, Loader2, RotateCcw, AlertCircle, ArrowLeft, FileAudio, X, Plus, Mic, Music,
} from "lucide-react";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { getTool, ACCENTS } from "../config/tools";
import { useMediaJob, jobErrorText } from "../hooks/useMediaJob";
import { mergeAudio, getVideoShorts } from "../api/videos";
import { downloadShortBlob, getShortStreamUrl } from "../api/shorts";
import { extractApiError } from "../utils/format";

const AUDIO_RE = /\.(mp3|wav|m4a|aac|ogg|flac|opus)$/i;
const isAudio = f => f && (f.type.startsWith("audio/") || AUDIO_RE.test(f.name));

/** A completed merge always has exactly one short. */
async function loadMerged(jobId) {
  const { data } = await getVideoShorts(jobId);
  const short = (data ?? [])[0];
  if (!short) throw new Error("no short");
  return short;
}

export default function AudioMergePage() {
  const { t } = useTranslation();
  const { op } = useParams();
  const tool = getTool("audio", op);

  const [files, setFiles] = useState([]);     // concat: ordered list
  const [crossfade, setCrossfade] = useState(0); // concat: blend seconds (0 = hard cut)
  const [voice, setVoice] = useState(null);   // mix: main track
  const [music, setMusic] = useState(null);   // mix: background
  const [musicVolume, setMusicVolume] = useState(0.25);
  const [loading, setLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState("");
  const [localError, setLocalError] = useState("");
  const { job, result, error: jobError, isProcessing, start, reset: resetJob } =
    useMediaJob(loadMerged);
  const addRef = useRef(null);
  const voiceRef = useRef(null);
  const musicRef = useRef(null);

  if (!tool || (op !== "concat" && op !== "mix")) return <Navigate to="/tools" replace />;

  const accent = ACCENTS.amber;
  const Icon = tool.icon;

  function addConcatFiles(list) {
    const valid = Array.from(list).filter(isAudio);
    if (!valid.length) { toast.error(t("media.onlyAudio")); return; }
    setFiles(f => [...f, ...valid]); setLocalError("");
  }
  function pickSingle(f, setter) {
    if (isAudio(f)) { setter(f); setLocalError(""); }
    else toast.error(t("media.onlyAudio"));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLocalError(""); setError("");
    let payloadFiles, params = {};
    if (op === "concat") {
      if (files.length < 2) { setLocalError(t("audioMerge.needTwo")); return; }
      payloadFiles = files;
      params = { crossfade };
    } else {
      if (!voice || !music) { setLocalError(t("audioMerge.needBoth")); return; }
      payloadFiles = [voice, music];
      params = { music_volume: musicVolume };
    }
    setLoading(true); setUploadProgress(0);
    try {
      const { data } = await mergeAudio(payloadFiles, op, params, setUploadProgress);
      start(data);
    } catch (err) {
      setError(extractApiError(err));
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    resetJob(); setFiles([]); setVoice(null); setMusic(null);
    setLocalError(""); setError("");
  }
  async function download() {
    if (!result) return;
    await downloadShortBlob(result.id, `${op}.mp3`);
  }

  return (
    <div className="max-w-xl mx-auto flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-start gap-3">
        <Link to="/tools" className="mt-1 text-zinc-600 hover:text-zinc-300 transition-colors"><ArrowLeft size={18} /></Link>
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
            <audio src={getShortStreamUrl(result.id)} controls className="w-full" />
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
            {op === "concat" ? (
              <div className="flex flex-col gap-3">
                <input ref={addRef} type="file" accept="audio/*" multiple className="hidden"
                  onChange={e => { addConcatFiles(e.target.files); e.target.value = ""; }} />
                {files.length > 0 && (
                  <div className="flex flex-col gap-2">
                    {files.map((f, i) => (
                      <div key={i} className="flex items-center gap-2.5 rounded-xl bg-white/[0.03] border border-white/[0.07] px-3 py-2">
                        <span className="w-5 h-5 rounded-md bg-amber-500/15 text-amber-300 text-[11px] font-bold flex items-center justify-center shrink-0">{i + 1}</span>
                        <FileAudio size={15} className="text-zinc-500 shrink-0" />
                        <span className="text-sm text-zinc-300 truncate flex-1">{f.name}</span>
                        <button type="button" onClick={() => setFiles(list => list.filter((_, j) => j !== i))}
                          className="text-zinc-600 hover:text-red-400 transition-colors"><X size={14} /></button>
                      </div>
                    ))}
                  </div>
                )}
                <button type="button" onClick={() => addRef.current?.click()}
                  className="flex items-center justify-center gap-2 rounded-xl border-2 border-dashed border-white/10
                    hover:border-amber-500/30 hover:bg-amber-500/3 py-4 text-sm text-zinc-400 transition-all">
                  <Plus size={16} /> {t("audioMerge.addAudio")}
                </button>
                <p className="text-[11px] text-zinc-600">{t("audioMerge.concatHint")}</p>
                {files.length >= 2 && (
                  <div className="flex flex-col gap-1.5 mt-1">
                    <div className="flex items-center justify-between">
                      <label className="text-sm font-medium text-zinc-300">{t("audioMerge.crossfade")}</label>
                      <span className="text-sm tabular-nums text-amber-300">
                        {crossfade > 0 ? `${crossfade.toFixed(1)}s` : t("audioMerge.crossfadeOff")}
                      </span>
                    </div>
                    <input type="range" min={0} max={5} step={0.5} value={crossfade}
                      onChange={e => setCrossfade(Number(e.target.value))}
                      className="w-full accent-amber-500 cursor-pointer" />
                  </div>
                )}
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                {/* voice */}
                <div>
                  <label className="text-sm font-medium text-zinc-300 mb-1.5 flex items-center gap-1.5">
                    <Mic size={14} className="text-amber-400" /> {t("audioMerge.voice")}
                  </label>
                  <input ref={voiceRef} type="file" accept="audio/*" className="hidden"
                    onChange={e => e.target.files[0] && pickSingle(e.target.files[0], setVoice)} />
                  <button type="button" onClick={() => voiceRef.current?.click()}
                    className={`w-full text-left text-sm rounded-xl px-3.5 py-2.5 border transition-colors truncate
                      ${voice ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300" : "border-white/10 bg-white/[0.04] text-zinc-500 hover:border-white/20"}`}>
                    {voice ? voice.name : t("audioMerge.chooseVoice")}
                  </button>
                </div>
                {/* music */}
                <div>
                  <label className="text-sm font-medium text-zinc-300 mb-1.5 flex items-center gap-1.5">
                    <Music size={14} className="text-amber-400" /> {t("audioMerge.music")}
                  </label>
                  <input ref={musicRef} type="file" accept="audio/*" className="hidden"
                    onChange={e => e.target.files[0] && pickSingle(e.target.files[0], setMusic)} />
                  <button type="button" onClick={() => musicRef.current?.click()}
                    className={`w-full text-left text-sm rounded-xl px-3.5 py-2.5 border transition-colors truncate
                      ${music ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300" : "border-white/10 bg-white/[0.04] text-zinc-500 hover:border-white/20"}`}>
                    {music ? music.name : t("audioMerge.chooseMusic")}
                  </button>
                </div>
                {/* music volume */}
                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-sm font-medium text-zinc-300">{t("tf.music_volume")}</label>
                    <span className="text-sm tabular-nums text-amber-300">{Math.round(musicVolume * 100)}%</span>
                  </div>
                  <input type="range" min={0} max={1} step={0.05} value={musicVolume}
                    onChange={e => setMusicVolume(Number(e.target.value))}
                    className="w-full accent-amber-500 cursor-pointer" />
                </div>
              </div>
            )}

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

            <Button type="submit" loading={loading} size="lg"><Upload size={18} /> {t("toolRun.run")}</Button>
          </form>
        </Card>
      )}
    </div>
  );
}
