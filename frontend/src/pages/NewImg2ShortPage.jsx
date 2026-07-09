import { useState, useRef, useEffect } from "react";
import { Film, Upload, Download, Loader2, RotateCcw, AlertCircle, X, Images } from "lucide-react";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { useMediaJob, jobErrorText } from "../hooks/useMediaJob";
import { loadImageResult } from "../utils/imageJob";
import { extractApiError } from "../utils/format";
import { submitImageToShorts, getImage, getImageStreamUrl, downloadImageBlob } from "../api/images";

function isImage(f) {
  return f && (f.type.startsWith("image/") || /\.(png|jpg|jpeg|webp|bmp)$/i.test(f.name));
}

export default function NewImg2ShortPage() {
  const { t } = useTranslation();
  const [files, setFiles] = useState([]);
  const [previews, setPreviews] = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState("");
  const { job, result, error: jobError, isProcessing, start, reset: resetJob } =
    useMediaJob(loadImageResult, getImage);
  const fileRef = useRef(null);

  // Build object URLs once per file-list change and revoke them on cleanup so
  // we don't leak a new blob URL on every render.
  useEffect(() => {
    const urls = files.map((f) => URL.createObjectURL(f));
    setPreviews(urls);
    return () => urls.forEach((u) => URL.revokeObjectURL(u));
  }, [files]);

  function addFiles(list) {
    const picked = Array.from(list || []).filter(isImage);
    if (!picked.length) { toast.error(t("img2short.onlyImage")); return; }
    setFiles((prev) => [...prev, ...picked]);
    setError("");
  }

  function removeAt(i) {
    setFiles((prev) => prev.filter((_, idx) => idx !== i));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    if (!files.length) { setError(t("img2short.errors.noFiles")); return; }
    setLoading(true); setUploadProgress(0);
    try {
      const { data } = await submitImageToShorts(files, setUploadProgress);
      start(data);
    } catch (err) {
      setError(extractApiError(err));
    } finally {
      setLoading(false);
    }
  }

  function reset() { resetJob(); setFiles([]); setError(""); }

  async function download() {
    if (!result) return;
    await downloadImageBlob(result.id, "short.mp4");
  }

  return (
    <div className="max-w-xl mx-auto flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">{t("img2short.title")}</h1>
        <p className="text-zinc-500 mt-1 text-sm">{t("img2short.subtitle")}</p>
      </div>

      {(job?.status === "completed" && result) ? (
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between px-1">
            <span className="text-sm font-semibold text-emerald-400">{t("img2short.done")}</span>
            <button onClick={reset} className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 transition-colors">
              <RotateCcw size={13} /> {t("img2short.new")}
            </button>
          </div>
          <Card>
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-rose-500/12 border border-rose-500/20 flex items-center justify-center">
                  <Film size={16} className="text-rose-400" />
                </div>
                <span className="font-semibold text-zinc-200">{t("img2short.result")}</span>
              </div>
              <div className="rounded-xl overflow-hidden flex items-center justify-center bg-black/30">
                <video src={getImageStreamUrl(result.id)} controls className="max-h-[460px] max-w-full rounded-lg" />
              </div>
              <Button onClick={download} variant="secondary" size="sm">
                <Download size={15} /> {t("img2short.download")}
              </Button>
            </div>
          </Card>
        </div>
      ) : (job?.status === "failed" || jobError) ? (
        <Card>
          <div className="flex flex-col items-center gap-4 py-10 text-center">
            <AlertCircle size={32} className="text-red-400" />
            <p className="text-sm text-zinc-400">{jobErrorText(t, job, jobError, "img2short.failed")}</p>
            <Button size="sm" variant="secondary" onClick={reset}>{t("img2short.new")}</Button>
          </div>
        </Card>
      ) : isProcessing ? (
        <Card>
          <div className="flex flex-col items-center gap-4 py-12 text-center">
            <Loader2 size={32} className="text-rose-400 animate-spin" />
            <div>
              <p className="font-medium text-zinc-200">{t("img2short.processing")}</p>
              <p className="text-sm text-zinc-600 mt-1">{t("img2short.processingHint")} · {job.progress_percent ?? 0}%</p>
            </div>
          </div>
        </Card>
      ) : (
        <Card>
          <form onSubmit={handleSubmit} className="flex flex-col gap-5">
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => { e.preventDefault(); setDragOver(false); addFiles(e.dataTransfer.files); }}
              onClick={() => fileRef.current?.click()}
              className={`flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed
                p-8 cursor-pointer transition-all duration-200
                ${dragOver ? "drag-over" : "border-white/10 hover:border-rose-500/30 hover:bg-rose-500/3"}`}
            >
              <input ref={fileRef} type="file" accept="image/*" multiple className="hidden"
                onChange={(e) => addFiles(e.target.files)} />
              <div className="w-12 h-12 rounded-xl flex items-center justify-center bg-rose-500/10 border border-rose-500/20">
                <Upload size={22} className="text-rose-400" />
              </div>
              <div className="text-center">
                <p className="text-sm text-zinc-400">{t("img2short.drop")}</p>
                <p className="text-xs text-zinc-600 mt-1">{t("img2short.formats")}</p>
              </div>
            </div>

            {files.length > 0 && (
              <div className="flex flex-col gap-2">
                <div className="flex items-center gap-2 text-xs text-zinc-500">
                  <Images size={13} /> {t("img2short.count", { count: files.length })}
                </div>
                <div className="grid grid-cols-4 gap-2">
                  {files.map((f, i) => (
                    <div key={i} className="relative group aspect-square rounded-lg overflow-hidden border border-white/10">
                      <img src={previews[i]} alt={f.name} className="w-full h-full object-cover" />
                      <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); removeAt(i); }}
                        className="absolute top-1 right-1 w-5 h-5 rounded-full bg-black/60 text-white flex items-center justify-center
                          opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <X size={12} />
                      </button>
                      <span className="absolute bottom-0 left-0 px-1 text-[10px] bg-black/50 text-white">{i + 1}</span>
                    </div>
                  ))}
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

            <div className="flex items-start gap-2.5 rounded-xl bg-rose-500/5 border border-rose-500/15 px-4 py-3">
              <Film size={14} className="text-rose-400 mt-0.5 shrink-0" />
              <p className="text-xs text-zinc-500">{t("img2short.info")}</p>
            </div>

            {error && (
              <div className="rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">{error}</div>
            )}

            <Button type="submit" loading={loading} size="lg">
              <Film size={18} /> {t("img2short.submit")}
            </Button>
          </form>
        </Card>
      )}
    </div>
  );
}
