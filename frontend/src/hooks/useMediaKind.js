import { useLocation } from "react-router-dom";

const VIDEO_RE = /\.(mp4|mov|avi|mkv|webm|m4v)$/i;
const AUDIO_RE = /\.(mp3|wav|m4a|aac|ogg|flac|opus)$/i;

/**
 * Shared tools (cleanup / separate / dub) live under both /video/* and /audio/*.
 * The section in the URL decides which media the tool accepts: the Video section
 * only takes video, the Audio section only takes audio. Everything else (drop
 * copy, format hint, error message) follows from `kind`.
 */
export function useMediaKind() {
  const { pathname } = useLocation();
  const kind = pathname.startsWith("/audio") ? "audio" : "video";
  const isAudio = kind === "audio";

  function isAllowed(f) {
    if (!f) return false;
    return isAudio
      ? f.type.startsWith("audio/") || AUDIO_RE.test(f.name)
      : f.type.startsWith("video/") || VIDEO_RE.test(f.name);
  }

  return {
    kind,
    isAudio,
    isVideo: !isAudio,
    accept: isAudio ? "audio/*" : "video/*",
    isAllowed,
  };
}
