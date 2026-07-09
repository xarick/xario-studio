// Build downloadable transcript files from timed segments [{start, end, text}].

function pad(n, w = 2) {
  return String(Math.floor(n)).padStart(w, "0");
}

function clock(sec, ms = ".") {
  // Derive everything from total rounded milliseconds so a value like 7.9999
  // carries correctly to 00:00:08,000 instead of an invalid ",1000".
  let total = Math.max(0, Math.round(sec * 1000));
  const millis = total % 1000;
  total = Math.floor(total / 1000);
  const s = total % 60;
  total = Math.floor(total / 60);
  const m = total % 60;
  const h = Math.floor(total / 60);
  return `${pad(h)}:${pad(m)}:${pad(s)}${ms}${pad(millis, 3)}`;
}

// TXT with timestamps: [HH:MM:SS] text
export function toTxt(segments) {
  return segments
    .map((s) => `[${clock(s.start).split(".")[0]}] ${s.text}`)
    .join("\n");
}

// Plain text, no timestamps
export function toPlain(segments) {
  return segments.map((s) => s.text).join("\n");
}

export function toSrt(segments) {
  return segments
    .map((s, i) => `${i + 1}\n${clock(s.start, ",")} --> ${clock(s.end, ",")}\n${s.text}\n`)
    .join("\n");
}

export function toVtt(segments) {
  const body = segments
    .map((s) => `${clock(s.start)} --> ${clock(s.end)}\n${s.text}\n`)
    .join("\n");
  return `WEBVTT\n\n${body}`;
}

export function downloadText(filename, content) {
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
