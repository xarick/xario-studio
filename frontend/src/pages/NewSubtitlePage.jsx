import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Upload, Captions, ChevronRight, Sparkles, FileVideo, Languages, X } from "lucide-react";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Select } from "../components/ui/Select";
import { useVideo } from "../hooks/useVideo";
import { isVideoFile } from "../utils/validators";

const SUB_LANGS = [
  { value: "",   label: "Auto" },
  { value: "uz", label: "O‘zbekcha" },
  { value: "ru", label: "Русский" },
  { value: "en", label: "English" },
  { value: "tr", label: "Türkçe" },
];

export default function NewSubtitlePage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { submitSubtitle, loading, uploadProgress, error } = useVideo();
  const [file, setFile] = useState(null);
  const [text, setText] = useState("");
  const [lang, setLang] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [localError, setLocalError] = useState("");
  const fileRef = useRef(null);

  const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;

  function onDrop(e) {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f && isVideoFile(f)) setFile(f);
    else toast.error(t("newVideo.onlyVideo"));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLocalError("");
    if (!file) { setLocalError(t("newVideo.errors.noFile")); return; }
    if (!isVideoFile(file)) { setLocalError(t("newVideo.errors.invalidFile")); return; }
    if (!text.trim()) { setLocalError(t("subtitlePage.errors.noText")); return; }

    const video = await submitSubtitle(file, text.trim(), lang);
    if (video?.id) {
      toast.success(t("newVideo.submitted"));
      navigate(`/job/${video.id}`);
    }
  }

  return (
    <div className="max-w-xl mx-auto flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-start gap-3">
        <div className="w-11 h-11 rounded-xl bg-violet-500/12 border border-violet-500/20 flex items-center justify-center shrink-0">
          <Captions size={20} className="text-violet-400" strokeWidth={1.8} />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-2xl font-bold text-zinc-100">{t("subtitlePage.title")}</h1>
            <span className="text-[10px] bg-emerald-500/12 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded-full font-semibold uppercase tracking-wide">
              {t("subtitlePage.anyFormat")}
            </span>
          </div>
          <p className="text-zinc-500 mt-1 text-sm">{t("subtitlePage.subtitle")}</p>
        </div>
      </div>

      {/* How it works */}
      <div className="rounded-2xl bg-white/[0.02] border border-white/[0.06] px-4 py-3.5">
        <div className="flex items-center gap-1.5 mb-2.5">
          <Sparkles size={13} className="text-violet-400" />
          <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wide">{t("subtitlePage.howTitle")}</span>
        </div>
        <ol className="flex flex-col gap-1.5">
          {[t("subtitlePage.step1"), t("subtitlePage.step2"), t("subtitlePage.step3")].map((step, i) => (
            <li key={i} className="flex items-start gap-2.5 text-xs text-zinc-500">
              <span className="w-4 h-4 rounded-full bg-violet-500/15 text-violet-300 text-[10px] font-bold flex items-center justify-center shrink-0 mt-px">
                {i + 1}
              </span>
              <span className="leading-relaxed">{step}</span>
            </li>
          ))}
        </ol>
      </div>

      <Card>
        <form onSubmit={handleSubmit} className="flex flex-col gap-6">
          {/* Video file */}
          <div>
            <p className="text-sm font-medium text-zinc-300 mb-1">{t("subtitlePage.videoLabel")}</p>
            <p className="text-[11px] text-zinc-600 mb-2">{t("subtitlePage.videoHint")}</p>
            <div
              onDragOver={e => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
              onClick={() => !file && fileRef.current?.click()}
              className={`flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed
                p-8 transition-all duration-200
                ${dragOver ? "drag-over" : "border-white/10 hover:border-violet-500/30 hover:bg-violet-500/3"}
                ${file ? "border-emerald-500/30 bg-emerald-500/5 cursor-default" : "cursor-pointer"}`}
            >
              <input ref={fileRef} type="file" accept="video/*" className="hidden"
                onChange={e => e.target.files[0] && setFile(e.target.files[0])} />
              <div className={`w-11 h-11 rounded-xl flex items-center justify-center
                ${file ? "bg-emerald-500/15" : "bg-violet-500/10 border border-violet-500/20"}`}>
                {file ? <FileVideo size={20} className="text-emerald-400" /> : <Upload size={20} className="text-violet-400" />}
              </div>
              {file ? (
                <div className="text-center">
                  <p className="font-medium text-zinc-200 text-sm">{file.name}</p>
                  <p className="text-xs text-zinc-500 mt-0.5">{(file.size/1024/1024).toFixed(1)} MB</p>
                  <button type="button" onClick={() => setFile(null)}
                    className="mt-2 inline-flex items-center gap-1 text-xs text-zinc-600 hover:text-red-400 transition-colors">
                    <X size={12} /> {t("newVideo.chooseOther")}
                  </button>
                </div>
              ) : (
                <div className="text-center">
                  <p className="text-sm text-zinc-400">{t("newVideo.dropFile")}</p>
                  <p className="text-xs text-zinc-600 mt-1">{t("newVideo.orClick")}</p>
                </div>
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

          {/* Transcript text */}
          <div className="flex flex-col gap-2">
            <label htmlFor="transcript" className="text-sm font-semibold text-zinc-200">
              {t("subtitlePage.textLabel")}
            </label>
            <textarea
              id="transcript"
              value={text}
              onChange={e => setText(e.target.value)}
              rows={7}
              placeholder={t("subtitlePage.textPlaceholder")}
              className="w-full rounded-xl bg-white/[0.03] border border-white/[0.08] px-4 py-3 text-sm text-zinc-200
                placeholder:text-zinc-600 focus:outline-none focus:border-violet-500/40 resize-y leading-relaxed"
            />
            <div className="flex items-center justify-between">
              <p className="text-[11px] text-zinc-600">{t("subtitlePage.textHint")}</p>
              <span className="text-[11px] text-zinc-600 tabular-nums">{wordCount} {t("subtitlePage.words")}</span>
            </div>
          </div>

          {/* Language */}
          <div className="flex items-center justify-between gap-4 px-4 py-3 rounded-xl bg-white/[0.02] border border-white/[0.05]">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-violet-500/12 border border-violet-500/20 flex items-center justify-center">
                <Languages size={15} className="text-violet-400" strokeWidth={1.8} />
              </div>
              <label className="text-sm font-medium text-zinc-300">{t("newVideo.subtitleLang")}</label>
            </div>
            <Select value={lang} onChange={setLang} options={SUB_LANGS} className="w-40" />
          </div>

          {/* Info */}
          <div className="flex items-start gap-2.5 rounded-xl bg-blue-500/5 border border-blue-500/15 px-4 py-3">
            <Sparkles size={14} className="text-blue-400 mt-0.5 shrink-0" />
            <p className="text-xs text-zinc-500 leading-relaxed">{t("subtitlePage.info")}</p>
          </div>

          {(localError || error) && (
            <div className="rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
              {localError || error}
            </div>
          )}

          <Button type="submit" loading={loading} size="lg">
            <Captions size={18} />
            {t("subtitlePage.submit")}
            <ChevronRight size={16} />
          </Button>
        </form>
      </Card>
    </div>
  );
}
