export function isValidUrl(str) {
  try {
    new URL(str);
    return true;
  } catch {
    return false;
  }
}

export function isVideoFile(file) {
  const allowed = ["video/mp4", "video/quicktime", "video/x-msvideo", "video/webm", "video/x-matroska"];
  return allowed.includes(file.type) || /\.(mp4|mov|avi|mkv|webm|m4v)$/i.test(file.name);
}
