import {
  Minimize2, Gauge, Film, Music, Crop, Scissors,
  Volume2, AudioWaveform, Maximize, RefreshCw, Stamp, Wand2, ZoomIn,
  Combine, Layers,
} from "lucide-react";

/**
 * Tool registry. Each tool maps to a backend `op` (videos/tool or images/tool).
 * `id` is unique across sections (used for i18n + hub keys); `op` is what the
 * backend receives. Fields are rendered generically by the tool pages.
 *
 * field.type: "range" | "number" | "select"
 *   select option labels can be i18n keys when option.i18n is true.
 */
export const TOOLS = [
  // ── Video (ffmpeg) ─────────────────────────────────────────────
  { id: "compress", op: "compress", section: "video", icon: Minimize2, accent: "violet",
    fields: [{ key: "crf", type: "range", min: 23, max: 34, step: 1, default: 28, label: "tf.crf" }] },
  { id: "speed", op: "speed", section: "video", icon: Gauge, accent: "violet",
    fields: [{ key: "factor", type: "select", default: 1, label: "tf.speed", options: [
      { value: 0.5, label: "0.5×" }, { value: 0.75, label: "0.75×" }, { value: 1, label: "1×" },
      { value: 1.25, label: "1.25×" }, { value: 1.5, label: "1.5×" }, { value: 2, label: "2×" }] }] },
  { id: "gif", op: "gif", section: "video", icon: Film, accent: "violet",
    fields: [
      { key: "start", type: "number", default: 0, min: 0, step: 0.5, label: "tf.start", unit: "s" },
      { key: "end", type: "number", default: 5, min: 0.5, step: 0.5, label: "tf.end", unit: "s" },
      { key: "fps", type: "range", min: 5, max: 24, step: 1, default: 12, label: "tf.fps" },
      { key: "width", type: "select", default: 480, label: "tf.width", options: [
        { value: 320, label: "320" }, { value: 480, label: "480" }, { value: 640, label: "640" }] }] },
  { id: "extract_audio", op: "extract_audio", section: "video", icon: Music, accent: "violet", fields: [] },
  { id: "aspect", op: "aspect", section: "video", icon: Crop, accent: "violet",
    fields: [
      { key: "aspect", type: "select", default: "9:16", label: "tf.aspect", options: [
        { value: "9:16", label: "9:16" }, { value: "1:1", label: "1:1" }, { value: "16:9", label: "16:9" }] },
      { key: "fit", type: "select", default: "crop", label: "tf.fit", options: [
        { value: "crop", label: "editor.fitCrop", i18n: true }, { value: "pad", label: "editor.fitPad", i18n: true }] }] },
  { id: "watermark", op: "watermark", section: "video", icon: Stamp, accent: "violet",
    extraFile: { label: "tf.logo", accept: "image/*" },
    fields: [
      { key: "position", type: "select", default: "bottom-right", label: "tf.position", options: [
        { value: "top-left", label: "tf.posTopLeft", i18n: true },
        { value: "top-right", label: "tf.posTopRight", i18n: true },
        { value: "bottom-left", label: "tf.posBottomLeft", i18n: true },
        { value: "bottom-right", label: "tf.posBottomRight", i18n: true },
        { value: "center", label: "tf.posCenter", i18n: true }] },
      { key: "scale", type: "range", min: 0.05, max: 0.5, step: 0.05, default: 0.2, label: "tf.scale" },
      { key: "opacity", type: "range", min: 0.1, max: 1, step: 0.1, default: 1, label: "tf.opacity" }] },

  // ── Audio (ffmpeg) ─────────────────────────────────────────────
  { id: "trim", op: "trim", section: "audio", icon: Scissors, accent: "amber",
    fields: [
      { key: "start", type: "number", default: 0, min: 0, step: 0.5, label: "tf.start", unit: "s" },
      { key: "end", type: "number", default: 30, min: 0.5, step: 0.5, label: "tf.end", unit: "s" }] },
  { id: "audio_convert", op: "convert", section: "audio", icon: RefreshCw, accent: "amber",
    fields: [{ key: "fmt", type: "select", default: "mp3", label: "tf.format", options: [
      { value: "mp3", label: "MP3" }, { value: "wav", label: "WAV" }, { value: "m4a", label: "M4A" },
      { value: "ogg", label: "OGG" }, { value: "flac", label: "FLAC" }] }] },
  { id: "volume", op: "volume", section: "audio", icon: Volume2, accent: "amber",
    fields: [{ key: "db", type: "range", min: -20, max: 20, step: 1, default: 6, label: "tf.volume", unit: "dB" }] },
  { id: "pitch", op: "pitch", section: "audio", icon: AudioWaveform, accent: "amber",
    fields: [{ key: "semitones", type: "range", min: -12, max: 12, step: 1, default: 0, label: "tf.pitch", unit: "st" }] },
  { id: "concat", op: "concat", section: "audio", icon: Combine, accent: "amber", route: "/audio/merge/concat", fields: [] },
  { id: "mix", op: "mix", section: "audio", icon: Layers, accent: "amber", route: "/audio/merge/mix", fields: [] },

  // ── Image (PIL) ────────────────────────────────────────────────
  { id: "crop", op: "crop", section: "image", icon: Crop, accent: "rose",
    fields: [{ key: "aspect", type: "select", default: "1:1", label: "tf.aspect", options: [
      { value: "1:1", label: "1:1" }, { value: "9:16", label: "9:16" }, { value: "16:9", label: "16:9" },
      { value: "4:3", label: "4:3" }, { value: "3:4", label: "3:4" }] }] },
  { id: "resize", op: "resize", section: "image", icon: Maximize, accent: "rose",
    fields: [{ key: "width", type: "number", default: 1080, min: 16, max: 8000, step: 1, label: "tf.width", unit: "px" }] },
  { id: "image_convert", op: "convert", section: "image", icon: RefreshCw, accent: "rose",
    fields: [{ key: "fmt", type: "select", default: "png", label: "tf.format", options: [
      { value: "png", label: "PNG" }, { value: "jpg", label: "JPG" }, { value: "webp", label: "WEBP" }] }] },
  { id: "enhance", op: "enhance", section: "image", icon: Wand2, accent: "rose",
    fields: [
      { key: "sharpness", type: "range", min: 0, max: 3, step: 0.1, default: 1.5, label: "tf.sharpness" },
      { key: "contrast", type: "range", min: 0.5, max: 2, step: 0.1, default: 1.1, label: "tf.contrast" },
      { key: "color", type: "range", min: 0, max: 2, step: 0.1, default: 1.1, label: "tf.color" }] },
  { id: "upscale", op: "upscale", section: "image", icon: ZoomIn, accent: "rose",
    fields: [{ key: "factor", type: "select", default: 2, label: "tf.factor", options: [
      { value: 2, label: "2×" }, { value: 4, label: "4×" }] }] },
];

export const ACCENTS = {
  violet: { text: "text-violet-400", bg: "bg-violet-500/10", border: "border-violet-500/20", chip: "bg-violet-500/12" },
  amber:  { text: "text-amber-400",  bg: "bg-amber-500/10",  border: "border-amber-500/20",  chip: "bg-amber-500/12" },
  rose:   { text: "text-rose-400",   bg: "bg-rose-500/10",   border: "border-rose-500/20",   chip: "bg-rose-500/12" },
};

export function getTool(section, op) {
  return TOOLS.find(t => t.section === section && t.op === op) || null;
}

export function toolsBySection(section) {
  return TOOLS.filter(t => t.section === section);
}

/** Default params object for a tool's fields. */
export function defaultParams(tool) {
  return Object.fromEntries(tool.fields.map(f => [f.key, f.default]));
}
