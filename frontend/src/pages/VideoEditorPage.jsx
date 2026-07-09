import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Upload, Scissors, ChevronRight, FileVideo, X, Wand2, Play, Pause,
  Type, RectangleHorizontal, RectangleVertical, Square, Maximize,
  Plus, Trash2, RotateCcw, Smartphone, Zap, SlidersHorizontal,
} from "lucide-react";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { useVideo } from "../hooks/useVideo";
import { isVideoFile } from "../utils/validators";

function fmt(s) {
  if (!Number.isFinite(s) || s < 0) return "0:00";
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${String(sec).padStart(2, "0")}`;
}

const ASPECTS = [
  { id: "9:16",     icon: RectangleVertical,   ratioClass: "aspect-[9/16] max-w-[300px]" },
  { id: "1:1",      icon: Square,              ratioClass: "aspect-square max-w-[440px]" },
  { id: "16:9",     icon: RectangleHorizontal, ratioClass: "aspect-video" },
  { id: "original", icon: Maximize,            ratioClass: "" },
];

const OUTPUT_MODES = [
  { id: "short",  icon: Zap },
  { id: "phone",  icon: Smartphone },
  { id: "custom", icon: SlidersHorizontal },
];

const POSITIONS = ["top", "center", "bottom"];
const TEXT_COLORS = ["#FFFFFF", "#000000", "#FACC15", "#EF4444", "#22C55E", "#3B82F6"];
const TEXT_SIZES = [
  { id: "S", scale: 0.75 }, { id: "M", scale: 1 }, { id: "L", scale: 1.4 }, { id: "XL", scale: 1.8 },
];
const SHORT_MAX = 60; // seconds

export default function VideoEditorPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { submitEditing, loading, uploadProgress, error } = useVideo();

  const [file, setFile] = useState(null);
  const [src, setSrc] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [duration, setDuration] = useState(0);
  // Kdenlive-style clips covering the whole source contiguously. Removed clips
  // are cut out; the rest are joined in order to form the montage.
  const [clips, setClips] = useState([]);           // [{start,end,removed}]
  const [playhead, setPlayhead] = useState(0);      // source time (seconds)
  const [outputMode, setOutputMode] = useState("short");
  const [aspect, setAspect] = useState("9:16");
  const [fit, setFit] = useState("crop");
  const [texts, setTexts] = useState([]);           // [{text,start,end,position,color,scale}] on montage timeline
  const [isPlaying, setIsPlaying] = useState(false);
  const [localError, setLocalError] = useState("");
  const videoRef = useRef(null);
  const fileRef = useRef(null);

  useEffect(() => {
    if (!file) { setSrc(""); return; }
    const url = URL.createObjectURL(file);
    setSrc(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  // ── Derived ────────────────────────────────────────────────────────────────
  const D = duration || 1;
  const keptClips = clips.filter(c => !c.removed);
  const keptTotal = keptClips.reduce((a, c) => a + (c.end - c.start), 0);
  const keptCount = keptClips.length;
  const selIdxRaw = clips.findIndex(c => playhead >= c.start && playhead < c.end);
  const selIdx = selIdxRaw < 0 ? Math.max(0, clips.length - 1) : selIdxRaw;
  const selClip = clips[selIdx];

  const effAspect = outputMode === "custom" ? aspect : "9:16";
  const activeAspect = ASPECTS.find(a => a.id === effAspect);
  const objFit = fit === "pad" || effAspect === "original" ? "object-contain" : "object-cover";
  const overOneMin = outputMode === "short" && keptTotal > SHORT_MAX + 0.05;

  // source time → montage (output) time
  function sourceToMontage(time) {
    let m = 0;
    for (const c of clips) {
      if (c.removed) continue;
      if (time >= c.end) m += c.end - c.start;
      else if (time >= c.start) return m + (time - c.start);
      else return m;
    }
    return m;
  }
  function montageToSource(mt) {
    let a = 0;
    for (const c of clips) {
      if (c.removed) continue;
      const d = c.end - c.start;
      if (mt < a + d) return c.start + (mt - a);
      a += d;
    }
    const lastKept = [...clips].reverse().find(c => !c.removed);
    return lastKept ? lastKept.end : 0;
  }
  const montageTime = sourceToMontage(playhead);

  // ── File handling ──────────────────────────────────────────────────────────
  function pickFile(f) {
    if (f && isVideoFile(f)) {
      setFile(f); setLocalError("");
      setDuration(0); setClips([]); setTexts([]); setPlayhead(0); setIsPlaying(false);
    } else {
      toast.error(t("media.onlyVideo"));
    }
  }
  function onLoadedMeta() {
    const d = videoRef.current?.duration || 0;
    setDuration(d);
    setClips([{ start: 0, end: d, removed: false }]);
    setTexts([]);
    setPlayhead(0);
  }

  // ── Playhead + montage playback (skips removed clips) ──────────────────────
  function seekSource(time) {
    const c = Math.max(0, Math.min(time, duration));
    setPlayhead(c);
    if (videoRef.current) videoRef.current.currentTime = c;
  }
  function nextKeptFrom(time) {
    for (const c of clips) {
      if (c.removed) continue;
      if (time < c.start) return c.start;   // jump forward to next kept clip
      if (time < c.end) return time;        // already inside a kept clip
    }
    return null;                            // nothing left → end
  }
  function togglePlay() {
    const v = videoRef.current;
    if (!v || !keptClips.length) return;
    if (isPlaying) { v.pause(); setIsPlaying(false); return; }
    let startT = nextKeptFrom(playhead);
    if (startT == null) startT = keptClips[0].start; // restart from first kept
    v.currentTime = startT; setPlayhead(startT);
    v.play(); setIsPlaying(true);
  }
  function onTimeUpdate() {
    const v = videoRef.current;
    if (!v) return;
    let t = v.currentTime;
    if (isPlaying) {
      const c = clips.find(cc => t >= cc.start && t < cc.end);
      if (!c || c.removed) {
        const ns = nextKeptFrom(t);
        if (ns == null) {
          v.pause(); setIsPlaying(false);
          setPlayhead(clips.length ? clips[clips.length - 1].end : 0);
          return;
        }
        if (Math.abs(ns - t) > 0.01) { v.currentTime = ns; t = ns; }
      }
    }
    setPlayhead(t);
  }

  // ── Cut actions (razor + delete) ───────────────────────────────────────────
  function splitAtPlayhead() {
    setClips(list => {
      const out = [];
      for (const c of list) {
        if (playhead > c.start + 0.05 && playhead < c.end - 0.05) {
          out.push({ ...c, end: playhead });
          out.push({ start: playhead, end: c.end, removed: c.removed });
        } else {
          out.push(c);
        }
      }
      return out;
    });
  }
  function toggleRemoveSelected() {
    setClips(list => {
      const kept = list.filter(c => !c.removed).length;
      return list.map((c, i) => {
        if (i !== selIdx) return c;
        if (!c.removed && kept <= 1) return c; // never remove the last kept clip
        return { ...c, removed: !c.removed };
      });
    });
  }

  // ── Text overlays (on the montage timeline) ────────────────────────────────
  function addText() {
    const start = Math.min(montageTime, Math.max(0, keptTotal - 1));
    const end = Math.min(start + Math.min(3, keptTotal), keptTotal);
    setTexts(list => [...list, { text: "", start, end, position: "bottom", color: "#FFFFFF", scale: 1 }]);
  }
  function patchText(i, patch) {
    setTexts(list => list.map((tx, j) => {
      if (j !== i) return tx;
      const next = { ...tx, ...patch };
      if (next.end < next.start + 0.1) next.end = Math.min(next.start + 0.1, keptTotal);
      return next;
    }));
  }
  function removeText(i) { setTexts(list => list.filter((_, j) => j !== i)); }

  const activeTexts = texts.filter(tx => tx.text.trim() && montageTime >= tx.start && montageTime <= tx.end);

  // ── Submit ─────────────────────────────────────────────────────────────────
  async function handleSubmit(e) {
    e.preventDefault();
    setLocalError("");
    if (!file) { setLocalError(t("newVideo.errors.noFile")); return; }
    if (keptCount === 0 || keptTotal < 0.2) { setLocalError(t("editor.errors.range")); return; }
    if (overOneMin) { setLocalError(t("editor.errors.shortMax")); return; }
    const segments = keptClips.map(c => ({ start: +c.start.toFixed(3), end: +c.end.toFixed(3) }));
    const cleanTexts = texts
      .filter(tx => tx.text.trim() && tx.end > tx.start)
      .map(tx => ({ ...tx, text: tx.text.trim() }));
    const video = await submitEditing(file, { segments, texts: cleanTexts, aspect: effAspect, fit, outputMode });
    if (video?.id) {
      toast.success(t("newVideo.submitted"));
      navigate(`/job/${video.id}`);
    }
  }

  const posClass = (position) => position === "top" ? "top-3 items-start"
    : position === "center" ? "top-1/2 -translate-y-1/2 items-center"
    : "bottom-3 items-end";
  const montagePct = keptTotal ? (montageTime / keptTotal) * 100 : 0;

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-start gap-3">
        <div className="w-11 h-11 rounded-xl bg-violet-500/12 border border-violet-500/20 flex items-center justify-center shrink-0">
          <Scissors size={20} className="text-violet-400" strokeWidth={1.8} />
        </div>
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-2xl font-bold text-zinc-100">{t("editor.title")}</h1>
            <span className="text-[10px] bg-violet-500/12 text-violet-400 border border-violet-500/20 px-2 py-0.5 rounded-full font-semibold uppercase tracking-wide">
              {t("editor.badge")}
            </span>
          </div>
          <p className="text-zinc-500 mt-1 text-sm">{t("editor.subtitlePro")}</p>
        </div>
      </div>

      {!file ? (
        <Card>
          <div
            onDragOver={e => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={e => { e.preventDefault(); setDragOver(false); pickFile(e.dataTransfer.files[0]); }}
            onClick={() => fileRef.current?.click()}
            className={`flex flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed
              p-16 cursor-pointer transition-all duration-200
              ${dragOver ? "drag-over" : "border-white/10 hover:border-violet-500/30 hover:bg-violet-500/3"}`}
          >
            <input ref={fileRef} type="file" accept="video/*" className="hidden"
              onChange={e => e.target.files[0] && pickFile(e.target.files[0])} />
            <div className="w-14 h-14 rounded-xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center">
              <Upload size={24} className="text-violet-400" />
            </div>
            <div className="text-center">
              <p className="text-sm text-zinc-300 font-medium">{t("editor.upload")}</p>
              <p className="text-xs text-zinc-600 mt-1">{t("editor.uploadHint")}</p>
            </div>
          </div>
        </Card>
      ) : (
        <form onSubmit={handleSubmit} className="grid xl:grid-cols-[1fr_420px] gap-6 items-start">
          {/* ── Preview + cut timeline ──────────────────────────────────── */}
          <Card className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wide">{t("editor.preview")}</span>
              <button type="button" onClick={() => setFile(null)}
                className="inline-flex items-center gap-1 text-xs text-zinc-600 hover:text-red-400 transition-colors">
                <X size={12} /> {t("newVideo.chooseOther")}
              </button>
            </div>

            <div className="flex justify-center">
              <div className={`relative w-full ${activeAspect?.ratioClass || ""} mx-auto bg-black rounded-xl overflow-hidden`}>
                <video
                  ref={videoRef}
                  src={src}
                  onLoadedMetadata={onLoadedMeta}
                  onTimeUpdate={onTimeUpdate}
                  onPause={() => setIsPlaying(false)}
                  className={`w-full h-full ${objFit}`}
                />
                {activeTexts.map((tx, i) => (
                  <div key={i} className={`pointer-events-none absolute inset-x-0 flex flex-col px-4 ${posClass(tx.position)}`}>
                    <p className="max-w-full text-center mx-auto font-bold leading-tight
                      [text-shadow:_0_2px_6px_rgba(0,0,0,0.9)] whitespace-pre-wrap break-words"
                      style={{ color: tx.color, fontSize: `${1.25 * tx.scale}rem` }}>
                      {tx.text}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            {/* Transport (montage preview) */}
            <div className="flex items-center gap-3">
              <button type="button" onClick={togglePlay}
                className="w-10 h-10 rounded-full bg-violet-600 hover:bg-violet-500 text-white flex items-center justify-center transition-colors shrink-0">
                {isPlaying ? <Pause size={18} /> : <Play size={18} className="ml-0.5" />}
              </button>
              <div className="flex-1">
                <div className="relative h-2.5 rounded-full bg-white/8 cursor-pointer"
                  onClick={e => {
                    const r = e.currentTarget.getBoundingClientRect();
                    seekSource(montageToSource(((e.clientX - r.left) / r.width) * keptTotal));
                  }}>
                  <div className="absolute h-full rounded-full bg-violet-500/70" style={{ width: `${montagePct}%` }} />
                  <div className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3.5 h-3.5 rounded-full bg-white shadow"
                    style={{ left: `${montagePct}%` }} />
                </div>
              </div>
              <span className="text-[11px] text-zinc-400 tabular-nums shrink-0">
                {fmt(montageTime)} / {fmt(keptTotal)}
              </span>
            </div>

            {/* ── Cut timeline (Kdenlive-style razor + delete) ─────────────── */}
            <div className="flex flex-col gap-2 pt-1">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-zinc-300 flex items-center gap-1.5">
                  <Scissors size={13} className="text-violet-400" /> {t("editor.cutTitle")}
                </span>
                <span className="text-[11px] text-zinc-500">{t("editor.kept")}: {fmt(keptTotal)}</span>
              </div>

              {/* The whole source as one strip; click to move the playhead. */}
              <div className="relative h-14 rounded-lg bg-black/30 border border-white/[0.06] overflow-hidden cursor-pointer select-none"
                onClick={e => {
                  const r = e.currentTarget.getBoundingClientRect();
                  seekSource(((e.clientX - r.left) / r.width) * duration);
                }}>
                {clips.map((c, i) => {
                  const left = (c.start / D) * 100;
                  const width = ((c.end - c.start) / D) * 100;
                  return (
                    <div key={i}
                      className={`absolute top-0 h-full border-r-2 border-black/50 transition-colors pointer-events-none
                        ${c.removed
                          ? "bg-red-500/10 [background-image:repeating-linear-gradient(45deg,transparent,transparent_5px,rgba(239,68,68,0.18)_5px,rgba(239,68,68,0.18)_10px)]"
                          : "bg-violet-500/35"}
                        ${i === selIdx ? "ring-2 ring-inset ring-white/70 z-10" : ""}`}
                      style={{ left: `${left}%`, width: `${width}%` }}>
                      <span className={`text-[10px] font-bold absolute left-1 top-1 ${c.removed ? "text-red-300/70 line-through" : "text-white/90"}`}>
                        {i + 1}
                      </span>
                    </div>
                  );
                })}
                {/* playhead */}
                <div className="absolute top-0 h-full w-0.5 bg-white pointer-events-none z-20"
                  style={{ left: `${(playhead / D) * 100}%` }}>
                  <div className="w-2.5 h-2.5 rounded-full bg-white -ml-1 -mt-0.5" />
                </div>
              </div>

              {/* Razor + delete toolbar */}
              <div className="flex flex-wrap gap-2">
                <button type="button" onClick={splitAtPlayhead}
                  className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-violet-500/15 hover:bg-violet-500/25 text-violet-300 transition-colors">
                  <Scissors size={13} /> {t("editor.split")}
                </button>
                {selClip?.removed ? (
                  <button type="button" onClick={toggleRemoveSelected}
                    className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 transition-colors">
                    <RotateCcw size={13} /> {t("editor.restore")}
                  </button>
                ) : (
                  <button type="button" onClick={toggleRemoveSelected} disabled={keptCount <= 1}
                    className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-red-500/15 hover:bg-red-500/25 text-red-300 disabled:opacity-30 transition-colors">
                    <Trash2 size={13} /> {t("editor.remove")}
                  </button>
                )}
                <span className="text-[11px] text-zinc-600 self-center">{t("editor.pieceN", { n: selIdx + 1 })}</span>
              </div>
              <p className="text-[11px] text-zinc-600">{t("editor.cutHelp")}</p>
            </div>
          </Card>

          {/* ── Controls ────────────────────────────────────────────────── */}
          <div className="flex flex-col gap-4">
            {/* file chip */}
            <div className="glass p-3">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-emerald-500/15 flex items-center justify-center shrink-0">
                  <FileVideo size={16} className="text-emerald-400" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm text-zinc-200 truncate">{file.name}</p>
                  <p className="text-[11px] text-zinc-500">{(file.size/1024/1024).toFixed(1)} MB · {fmt(duration)}</p>
                </div>
              </div>
            </div>

            {/* Output mode */}
            <Card className="flex flex-col gap-3">
              <span className="text-xs font-semibold text-zinc-300">{t("editor.outputMode")}</span>
              <div className="grid grid-cols-3 gap-2">
                {OUTPUT_MODES.map(({ id, icon: Icon }) => {
                  const active = outputMode === id;
                  return (
                    <button key={id} type="button" onClick={() => setOutputMode(id)}
                      className={`flex flex-col items-center gap-1.5 py-2.5 rounded-xl border transition-all
                        ${active ? "border-violet-500/40 bg-violet-500/10 text-violet-300"
                                 : "border-white/8 bg-white/[0.02] text-zinc-500 hover:border-white/15"}`}>
                      <Icon size={18} strokeWidth={1.7} />
                      <span className="text-[10px] font-medium">{t(`editor.mode_${id}`)}</span>
                    </button>
                  );
                })}
              </div>
              <p className="text-[11px] text-zinc-600">{t(`editor.modeHint_${outputMode}`)}</p>

              {outputMode === "custom" && (
                <>
                  <div className="grid grid-cols-4 gap-2">
                    {ASPECTS.map(({ id, icon: Icon }) => (
                      <button key={id} type="button" onClick={() => setAspect(id)}
                        className={`flex flex-col items-center gap-1.5 py-2 rounded-xl border transition-all
                          ${aspect === id ? "border-violet-500/40 bg-violet-500/10 text-violet-300"
                                          : "border-white/8 bg-white/[0.02] text-zinc-500 hover:border-white/15"}`}>
                        <Icon size={16} strokeWidth={1.7} />
                        <span className="text-[10px] font-medium">{id === "original" ? t("editor.aspectOriginal") : id}</span>
                      </button>
                    ))}
                  </div>
                  {aspect !== "original" && (
                    <div className="flex gap-1.5 p-1 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                      {[["crop", t("editor.fitCrop")], ["pad", t("editor.fitPad")]].map(([id, label]) => (
                        <button key={id} type="button" onClick={() => setFit(id)}
                          className={`flex-1 py-1.5 rounded-lg text-xs font-semibold transition-all
                            ${fit === id ? "bg-violet-600 text-white" : "text-zinc-400 hover:text-zinc-200"}`}>
                          {label}
                        </button>
                      ))}
                    </div>
                  )}
                </>
              )}

              <div className={`flex items-center justify-between text-xs px-1 ${overOneMin ? "text-red-400" : "text-zinc-400"}`}>
                <span>{t("editor.totalLength")}</span>
                <span className="tabular-nums font-semibold">
                  {fmt(keptTotal)}{outputMode === "short" ? ` / ${fmt(SHORT_MAX)}` : ""}
                </span>
              </div>
            </Card>

            {/* Texts */}
            <Card className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-zinc-300 flex items-center gap-1.5">
                  <Type size={13} className="text-violet-400" /> {t("editor.texts")} ({texts.length})
                </span>
                <button type="button" onClick={addText}
                  className="inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded-lg bg-violet-500/15 hover:bg-violet-500/25 text-violet-300 transition-colors">
                  <Plus size={12} /> {t("editor.addText")}
                </button>
              </div>

              {texts.length === 0 && (
                <p className="text-[11px] text-zinc-600">{t("editor.textsHint")}</p>
              )}

              <div className="flex flex-col gap-3">
                {texts.map((tx, i) => (
                  <div key={i} className="rounded-xl border border-white/8 bg-white/[0.02] p-2.5 flex flex-col gap-2">
                    <div className="flex items-start gap-2">
                      <textarea value={tx.text} rows={2}
                        onChange={e => patchText(i, { text: e.target.value })}
                        placeholder={t("editor.textPlaceholder")}
                        className="flex-1 rounded-lg bg-white/[0.03] border border-white/[0.08] px-2.5 py-1.5 text-sm text-zinc-200
                          placeholder:text-zinc-600 focus:outline-none focus:border-violet-500/40 resize-none leading-snug" />
                      <button type="button" onClick={() => removeText(i)}
                        className="text-zinc-600 hover:text-red-400 transition-colors mt-1"><Trash2 size={13} /></button>
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-zinc-500 tabular-nums">
                      <span>{t("editor.from")} {fmt(tx.start)}</span>
                      <span>{t("editor.to")} {fmt(tx.end)}</span>
                    </div>
                    <input type="range" min={0} max={keptTotal || 0} step={0.1} value={tx.start}
                      onChange={e => patchText(i, { start: Number(e.target.value) })}
                      className="w-full accent-violet-500 cursor-pointer" />
                    <input type="range" min={0} max={keptTotal || 0} step={0.1} value={tx.end}
                      onChange={e => patchText(i, { end: Number(e.target.value) })}
                      className="w-full accent-violet-500 cursor-pointer" />

                    <div className="flex items-center gap-1.5 flex-wrap">
                      {POSITIONS.map(p => (
                        <button key={p} type="button" onClick={() => patchText(i, { position: p })}
                          className={`px-2 py-1 rounded-lg text-[10px] font-medium border transition-all
                            ${tx.position === p ? "border-violet-500/40 bg-violet-500/10 text-violet-300"
                                                : "border-white/8 text-zinc-500 hover:border-white/15"}`}>
                          {t(`editor.pos${p[0].toUpperCase()}${p.slice(1)}`)}
                        </button>
                      ))}
                    </div>

                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5">
                        {TEXT_COLORS.map(c => (
                          <button key={c} type="button" onClick={() => patchText(i, { color: c })} title={c}
                            className={`w-5 h-5 rounded-md border transition-all
                              ${tx.color.toUpperCase() === c ? "border-violet-400 scale-110" : "border-white/15 hover:border-white/40"}`}
                            style={{ backgroundColor: c }} />
                        ))}
                        <label className="relative w-5 h-5 rounded-md border border-white/15 overflow-hidden cursor-pointer"
                          style={{ backgroundColor: tx.color }}>
                          <input type="color" value={tx.color}
                            onChange={e => patchText(i, { color: e.target.value.toUpperCase() })}
                            className="absolute inset-0 opacity-0 cursor-pointer" />
                        </label>
                      </div>
                      <div className="flex gap-1">
                        {TEXT_SIZES.map(({ id, scale }) => (
                          <button key={id} type="button" onClick={() => patchText(i, { scale })}
                            className={`px-2 py-1 rounded-lg text-[10px] font-medium border transition-all
                              ${tx.scale === scale ? "border-violet-500/40 bg-violet-500/10 text-violet-300"
                                                   : "border-white/8 text-zinc-500 hover:border-white/15"}`}>
                            {t(`editor.size${id}`)}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>

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

            <Button type="submit" loading={loading} size="lg" disabled={overOneMin}>
              <Wand2 size={18} />
              {t("editor.submit")}
              <ChevronRight size={16} />
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
