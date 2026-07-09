/**
 * A completed image job must carry an output file. `useMediaJob` treats a throw
 * here as "the job finished but there is nothing to show", which surfaces an
 * error instead of silently returning the user to an empty submit form.
 */
export async function loadImageResult(_jobId, job) {
  if (!job?.output_ext) throw new Error("image job has no output");
  return job;
}

/**
 * Filename for a downloaded result. The geometry tools keep the source format,
 * so the extension comes from the job row rather than from the tool.
 */
export function downloadName(sourceName, suffix, job, fallbackExt = "png") {
  const base = (sourceName || suffix).replace(/\.[^.]+$/, "");
  return `${base}_${suffix}.${job?.output_ext ?? fallbackExt}`;
}
