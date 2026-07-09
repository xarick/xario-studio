import client from "./client";

export function listVideos(page = 1, limit = 20, { search = "", status = "", mode = "" } = {}) {
  const params = { page, limit };
  if (search) params.search = search;
  if (status) params.status = status;
  if (mode) params.mode = mode;
  return client.get("/api/v1/videos", { params });
}

export function submitVideoUrl(url, shortsCount, subtitlesEnabled = true, generationMode = "smart", subtitleLanguage = "") {
  return client.post("/api/v1/videos/url", {
    url,
    shorts_count: shortsCount,
    subtitles_enabled: subtitlesEnabled,
    subtitle_language: subtitleLanguage,
    generation_mode: generationMode,
  });
}

export function uploadVideoFile(file, shortsCount, onProgress, subtitlesEnabled = true, generationMode = "smart", subtitleLanguage = "") {
  const form = new FormData();
  form.append("file", file);
  form.append("shorts_count", shortsCount);
  form.append("subtitles_enabled", subtitlesEnabled);
  form.append("subtitle_language", subtitleLanguage);
  form.append("generation_mode", generationMode);
  return client.post("/api/v1/videos/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
}

// Subtitle-align mode: upload a video + the exact transcript; the backend
// force-aligns the text to the audio and burns subtitles onto the whole video.
export function uploadSubtitleVideo(file, transcriptText, language, onProgress) {
  const form = new FormData();
  form.append("file", file);
  form.append("shorts_count", 1);
  form.append("generation_mode", "subtitle");
  form.append("transcript_text", transcriptText);
  form.append("subtitle_language", language || "");
  form.append("subtitles_enabled", true);
  return client.post("/api/v1/videos/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
}

// Speech-to-text: upload an audio OR video file; the backend transcribes it
// into timed segments returned by getTranscript().
export function uploadTranscribeVideo(file, language, onProgress) {
  const form = new FormData();
  form.append("file", file);
  form.append("shorts_count", 1);
  form.append("generation_mode", "transcribe");
  form.append("subtitle_language", language || "");
  return client.post("/api/v1/videos/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
}

export function getTranscript(videoId) {
  return client.get(`/api/v1/videos/${videoId}/transcript`);
}

// Vocal/music separation (Demucs): upload audio OR video; backend splits into
// vocals + instrumental (+ karaoke video for video input).
export function uploadSeparateMedia(file, onProgress) {
  const form = new FormData();
  form.append("file", file);
  form.append("shorts_count", 1);
  form.append("generation_mode", "separate");
  return client.post("/api/v1/videos/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
}

// Audio cleanup: upload an audio OR video file; the backend normalises loudness,
// denoises, and (audio-only) trims silence, then returns the cleaned file.
export function uploadCleanupMedia(file, onProgress) {
  const form = new FormData();
  form.append("file", file);
  form.append("shorts_count", 1);
  form.append("generation_mode", "cleanup");
  return client.post("/api/v1/videos/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
}

// Text-to-speech (XTTS-v2): no media input — send text + language + a voice
// (a built-in speaker name, or an optional reference recording to clone).
export function submitTts(text, { language = "", voice = "", referenceAudio = null } = {}, onProgress) {
  const form = new FormData();
  form.append("text", text);
  form.append("language", language || "");
  form.append("voice", voice || "");
  if (referenceAudio) form.append("reference_audio", referenceAudio);
  return client.post("/api/v1/videos/tts", form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
}

// Translate + dub: upload audio/video; backend transcribes, translates to
// targetLanguage, re-voices (clones the original speaker unless `voice` is set),
// and muxes the new audio back.
export function submitDub(file, { targetLanguage, sourceLanguage = "", voice = "" } = {}, onProgress) {
  const form = new FormData();
  form.append("file", file);
  form.append("target_language", targetLanguage || "");
  form.append("source_language", sourceLanguage || "");
  form.append("voice", voice || "");
  return client.post("/api/v1/videos/dub", form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
}

// Manual montage (editor): upload a video + keep-segments + timed text overlays;
// the backend cuts & joins the segments, fits the aspect, and burns the captions.
// `segments`: [{start,end}] (source timeline). `texts`: [{text,start,end,position,color,scale}]
// (output/montage timeline). `outputMode`: "short" | "phone" | "custom".
export function uploadEditVideo(file, { segments = [], texts = [], aspect = "9:16", fit = "crop", outputMode = "custom" } = {}, onProgress) {
  const form = new FormData();
  form.append("file", file);
  form.append("aspect", aspect);
  form.append("fit", fit);
  form.append("output_mode", outputMode);
  form.append("segments", JSON.stringify(segments));
  form.append("texts", JSON.stringify(texts));
  return client.post("/api/v1/videos/edit", form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
}

// Single-purpose media tool: upload a video/audio file + op + JSON params.
// `extra` is an optional second file (e.g. the logo for the watermark tool).
export function uploadToolMedia(file, op, params = {}, onProgress, extra = null) {
  const form = new FormData();
  form.append("file", file);
  form.append("op", op);
  form.append("params", JSON.stringify(params));
  if (extra) form.append("extra", extra);
  return client.post("/api/v1/videos/tool", form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
}

// Audio merge: concat (N files end-to-end) or mix (voice + music). op + JSON params.
export function mergeAudio(files, op, params = {}, onProgress) {
  const form = new FormData();
  for (const f of files) form.append("files", f);
  form.append("op", op);
  form.append("params", JSON.stringify(params));
  return client.post("/api/v1/videos/merge", form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
}

// Video merge (montage): join N videos end-to-end with an optional animated
// transition (fade to black/white, dissolve, slide, wave…) between each cut.
export function mergeVideos(files, params = {}, onProgress, music = null) {
  const form = new FormData();
  for (const f of files) form.append("files", f);
  form.append("op", "vconcat");
  form.append("params", JSON.stringify(params));
  if (music) form.append("music", music);
  return client.post("/api/v1/videos/merge", form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
    },
  });
}

export function getVideo(videoId) {
  return client.get(`/api/v1/videos/${videoId}`);
}

export function deleteVideo(videoId) {
  return client.delete(`/api/v1/videos/${videoId}`);
}

export function getVideoShorts(videoId) {
  return client.get(`/api/v1/videos/${videoId}/shorts`);
}

export function getVideoStats() {
  return client.get("/api/v1/videos/stats");
}

export function analyzeVideoUrl(url) {
  return client.post("/api/v1/videos/analyze", { url });
}

/** Stop a queued or running job. Returns the updated video row. */
export function cancelVideo(videoId) {
  return client.post(`/api/v1/videos/${videoId}/cancel`);
}
