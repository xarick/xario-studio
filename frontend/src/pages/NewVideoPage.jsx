import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Link2, Upload, Scissors, ChevronRight, Info, CheckCircle2, Sparkles, Captions, Wand2, Film, MousePointer2 } from "lucide-react";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Select } from "../components/ui/Select";
import { useVideo } from "../hooks/useVideo";
import { isValidUrl, isVideoFile } from "../utils/validators";
import { analyzeVideoUrl } from "../api/videos";

export default function NewVideoPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { submitUrl, submitFile, loading, uploadProgress, error } = useVideo();
  const [mode, setMode] = useState("url");
  function switchMode(m) { setMode(m); setLocalError(""); }
  const [url, setUrl] = useState("");
  const [file, setFile] = useState(null);
  const [shorts, setShorts] = useState(3);
  const [localError, setLocalError] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [aiSuggestion, setAiSuggestion] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [subtitles, setSubtitles] = useState(false);
  const [subLang, setSubLang] = useState("");
  const [genMode, setGenMode] = useState("smart");
  const fileRef = useRef(null);

  async function handleAnalyze() {
    if (!isValidUrl(url)) return;
    setAnalyzing(true);
    setAiSuggestion(null);
    try {
      const res = await analyzeVideoUrl(url);
      setAiSuggestion(res.data);
    } catch {
      toast.error(t("newVideo.analysisError"));
    } finally {
      setAnalyzing(false);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLocalError("");

    if (shorts < 1 || shorts > 10) { setLocalError(t("newVideo.errors.shortsRange")); return; }

    const lang = subtitles ? subLang : "";
    let video = null;
    if (mode === "url") {
      if (!isValidUrl(url)) { setLocalError(t("newVideo.errors.invalidUrl")); return; }
      video = await submitUrl(url, shorts, subtitles, genMode, lang);
    } else {
      if (!file) { setLocalError(t("newVideo.errors.noFile")); return; }
      if (!isVideoFile(file)) { setLocalError(t("newVideo.errors.invalidFile")); return; }
      video = await submitFile(file, shorts, subtitles, genMode, lang);
    }
    if (video?.id) {
      toast.success(t("newVideo.submitted"));
      navigate(`/job/${video.id}`);
    }
  }

  function onDrop(e) {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f && isVideoFile(f)) { setFile(f); setMode("file"); }
    else toast.error(t("newVideo.onlyVideo"));
  }

  const MODES = [
    { id: "url",  icon: Link2,  title: t("newVideo.urlMode"),  sub: t("newVideo.urlSub") },
    { id: "file", icon: Upload, title: t("newVideo.fileMode"), sub: t("newVideo.fileSub") },
  ];

  // Ordered weak → strong (left → right): Simple, Smart, Pro.
  const GEN_MODES = [
    { id: "simple", icon: Film,          title: t("newVideo.simpleMode"), sub: t("newVideo.simpleSub") },
    { id: "smart",  icon: Wand2,         title: t("newVideo.smartMode"),  sub: t("newVideo.smartSub"),  badge: "AI" },
    { id: "pro",    icon: MousePointer2, title: t("newVideo.proMode"),    sub: t("newVideo.proSub"),    badge: "PRO" },
  ];

  const SUB_LANGS = [
    { value: "",   label: t("newVideo.langAuto") },
    { value: "uz", label: "O‘zbekcha" },
    { value: "ru", label: "Русский" },
    { value: "en", label: "English" },
    { value: "tr", label: "Türkçe" },
  ];

  return (
    <div className="max-w-xl mx-auto flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">{t("newVideo.title")}</h1>
        <p className="text-zinc-500 mt-1 text-sm">{t("newVideo.subtitle")}</p>
      </div>

      {/* ── Method (generation mode) — top-level tabs, extensible ────────── */}
      <div className="flex flex-col gap-2.5">
        <div className="flex gap-1.5 p-1.5 rounded-2xl bg-white/[0.03] border border-white/[0.06]">
          {GEN_MODES.map(({ id, icon: Icon, title, badge }) => {
            const active = genMode === id;
            return (
              <button
                key={id}
                type="button"
                onClick={() => setGenMode(id)}
                className={`flex-1 flex items-center justify-center gap-2 py-3 px-3 rounded-xl text-sm font-semibold
                  transition-all duration-200
                  ${active
                    ? "bg-violet-600 text-white shadow-lg shadow-violet-600/25"
                    : "text-zinc-400 hover:text-zinc-200 hover:bg-white/4"
                  }`}
              >
                <Icon size={17} strokeWidth={1.9} />
                {title}
                {badge && (
                  <span className={`text-[9px] px-1.5 py-px rounded font-bold uppercase tracking-wider
                    ${active ? "bg-white/20 text-white" : "bg-violet-500/15 text-violet-400"}`}>
                    {badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
        <p className="text-xs text-zinc-500 px-1">
          {t(`newVideo.${genMode}Sub`)}
        </p>
      </div>

      {/* Source switcher */}
      <div className="grid grid-cols-2 gap-3">
        {MODES.map(({ id, icon: Icon, title, sub }) => {
          const active = mode === id;
          return (
            <button
              key={id}
              onClick={() => switchMode(id)}
              className={`relative flex flex-col items-center gap-3 p-5 rounded-2xl border
                transition-all duration-200 overflow-hidden
                ${active
                  ? "border-violet-500/40 bg-violet-500/8 shadow-lg shadow-violet-500/10"
                  : "border-white/6 bg-white/[0.02] hover:border-white/12 hover:bg-white/3"
                }`}
            >
              {active && (
                <div className="absolute top-2.5 right-2.5 w-5 h-5 rounded-full bg-violet-600 flex items-center justify-center">
                  <CheckCircle2 size={11} className="text-white" strokeWidth={3} />
                </div>
              )}
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center transition-colors
                ${active ? "bg-violet-500/20" : "bg-white/5"}`}>
                <Icon size={19} className={active ? "text-violet-400" : "text-zinc-500"} strokeWidth={1.7} />
              </div>
              <div className="text-center">
                <p className={`text-sm font-semibold ${active ? "text-zinc-100" : "text-zinc-400"}`}>{title}</p>
                <p className="text-[11px] text-zinc-600 mt-0.5">{sub}</p>
              </div>
            </button>
          );
        })}
      </div>

      <Card>
        <form onSubmit={handleSubmit} className="flex flex-col gap-6">
          {mode === "url" ? (
            <div className="flex flex-col gap-2">
              <Input
                label="Video URL"
                type="text"
                placeholder="https://youtube.com/watch?v=..."
                icon={Link2}
                value={url}
                onChange={e => setUrl(e.target.value)}
                hint={t("newVideo.urlHint")}
              />
              {url && isValidUrl(url) && (
                <button type="button" onClick={handleAnalyze} disabled={analyzing}
                  className="flex items-center gap-1.5 text-xs text-violet-400 hover:text-violet-300 transition-colors disabled:opacity-50 self-start">
                  <Sparkles size={12} />
                  {analyzing ? t("newVideo.analyzing") : t("newVideo.aiSuggest")}
                </button>
              )}
            </div>
          ) : (
            <div>
              <p className="text-sm font-medium text-zinc-300 mb-2">{t("newVideo.fileMode")}</p>
              <div
                onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={onDrop}
                onClick={() => fileRef.current?.click()}
                className={`flex flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed
                  p-10 cursor-pointer transition-all duration-200
                  ${dragOver ? "drag-over" : "border-white/10 hover:border-violet-500/30 hover:bg-violet-500/3"}
                  ${file ? "border-emerald-500/30 bg-emerald-500/5" : ""}`}
              >
                <input ref={fileRef} type="file" accept="video/*" className="hidden"
                  onChange={e => e.target.files[0] && setFile(e.target.files[0])} />
                {file ? (
                  <>
                    <div className="w-12 h-12 rounded-xl bg-emerald-500/15 flex items-center justify-center">
                      <Scissors size={22} className="text-emerald-400" />
                    </div>
                    <div className="text-center">
                      <p className="font-medium text-zinc-200 text-sm">{file.name}</p>
                      <p className="text-xs text-zinc-500 mt-1">{(file.size/1024/1024).toFixed(1)} MB</p>
                    </div>
                    <button type="button" onClick={e => { e.stopPropagation(); setFile(null); }}
                      className="text-xs text-zinc-600 hover:text-red-400 transition-colors">
                      {t("newVideo.chooseOther")}
                    </button>
                  </>
                ) : (
                  <>
                    <div className="w-12 h-12 rounded-xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center">
                      <Upload size={22} className="text-violet-400" />
                    </div>
                    <div className="text-center">
                      <p className="text-sm text-zinc-400">{t("newVideo.dropFile")}</p>
                      <p className="text-xs text-zinc-600 mt-1">{t("newVideo.orClick")}</p>
                    </div>
                  </>
                )}
              </div>

              {loading && uploadProgress > 0 && uploadProgress < 100 && (
                <div className="mt-3">
                  <div className="flex justify-between text-xs text-zinc-500 mb-1.5">
                    <span>{t("newVideo.uploading")}</span><span>{uploadProgress}%</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-white/5 overflow-hidden">
                    <div className="h-full progress-pulse rounded-full" style={{ width: `${uploadProgress}%` }} />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Shorts count — same for both modes; Smart auto-arranges the clips */}
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <label className="text-sm font-semibold text-zinc-200">{t("newVideo.shortsCount")}</label>
              <div className="flex items-center gap-1.5">
                <button type="button" onClick={() => setShorts(s => Math.max(1, s - 1))}
                  className="w-8 h-8 rounded-lg bg-white/5 hover:bg-white/10 text-zinc-300 font-bold transition-colors flex items-center justify-center">−</button>
                <span className="w-10 text-center text-2xl font-bold gradient-text tabular-nums">{shorts}</span>
                <button type="button" onClick={() => setShorts(s => Math.min(10, s + 1))}
                  className="w-8 h-8 rounded-lg bg-white/5 hover:bg-white/10 text-zinc-300 font-bold transition-colors flex items-center justify-center">+</button>
              </div>
            </div>
            <input type="range" min={1} max={10} value={shorts}
              onChange={e => setShorts(Number(e.target.value))}
              className="w-full h-2 rounded-full appearance-none cursor-pointer [&::-webkit-slider-track]:rounded-full [&::-webkit-slider-track]:bg-white/10 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-violet-500 [&::-webkit-slider-thumb]:shadow-lg [&::-webkit-slider-thumb]:shadow-violet-500/40 [&::-webkit-slider-thumb]:cursor-grab" />
            <div className="flex justify-between text-[11px] text-zinc-600">
              <span>1</span><span>5</span><span>10</span>
            </div>
            {aiSuggestion && (
              <div className="flex items-start justify-between gap-3 rounded-xl bg-violet-500/8 border border-violet-500/20 px-4 py-3">
                <div className="flex items-start gap-2">
                  <Sparkles size={14} className="text-violet-400 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-xs font-medium text-violet-300">
                      {t("newVideo.aiRecommends", { count: aiSuggestion.suggested_count })}
                    </p>
                    <p className="text-[11px] text-zinc-500 mt-0.5">{aiSuggestion.reason}</p>
                  </div>
                </div>
                <button type="button" onClick={() => setShorts(aiSuggestion.suggested_count)}
                  className="text-xs text-violet-400 hover:text-violet-300 font-medium shrink-0 transition-colors">
                  {t("newVideo.apply")}
                </button>
              </div>
            )}
          </div>

          {/* Subtitle toggle */}
          <div className="flex items-center justify-between gap-4 px-4 py-3.5 rounded-xl bg-white/[0.03] border border-white/[0.07]">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 transition-colors
                ${subtitles ? "bg-violet-500/15 border border-violet-500/25" : "bg-white/4 border border-white/8"}`}>
                <Captions size={15} className={subtitles ? "text-violet-400" : "text-zinc-600"} strokeWidth={1.8} />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className={`text-sm font-semibold transition-colors ${subtitles ? "text-zinc-200" : "text-zinc-500"}`}>
                    {t("newVideo.subtitles")}
                  </span>
                  {subtitles && (
                    <span className="text-[9px] bg-violet-500/15 text-violet-400 px-1.5 py-px rounded font-semibold uppercase tracking-wider">
                      AI
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-zinc-600 mt-0.5 truncate">{t("newVideo.subtitlesHint")}</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setSubtitles(s => !s)}
              className={`relative w-11 h-6 rounded-full shrink-0 transition-colors duration-200 focus:outline-none
                ${subtitles ? "bg-violet-600" : "bg-zinc-700/80"}`}
              role="switch"
              aria-checked={subtitles}
            >
              <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow-md transition-transform duration-200
                ${subtitles ? "translate-x-5" : "translate-x-0"}`}
              />
            </button>
          </div>

          {/* Subtitle language — only when subtitles are on */}
          {subtitles && (
            <div className="flex items-center justify-between gap-4 -mt-3 px-4 py-3 rounded-xl bg-white/[0.02] border border-white/[0.05]">
              <label className="text-xs font-medium text-zinc-400">
                {t("newVideo.subtitleLang")}
              </label>
              <Select value={subLang} onChange={setSubLang} options={SUB_LANGS} className="w-40" />
            </div>
          )}

          {/* Info */}
          <div className="flex items-start gap-2.5 rounded-xl bg-blue-500/5 border border-blue-500/15 px-4 py-3">
            <Info size={14} className="text-blue-400 mt-0.5 shrink-0" />
            <p className="text-xs text-zinc-500">
              {t(`newVideo.${genMode}Info`)}
            </p>
          </div>

          {(localError || error) && (
            <div className="rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
              {localError || error}
            </div>
          )}

          <Button type="submit" loading={loading} size="lg">
            <Scissors size={18} />
            {t("newVideo.submit")}
            <ChevronRight size={16} />
          </Button>
        </form>
      </Card>
    </div>
  );
}
