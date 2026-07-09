import { useState } from "react";
import { submitVideoUrl, uploadVideoFile, uploadSubtitleVideo, uploadTranscribeVideo, uploadCleanupMedia, uploadSeparateMedia, submitTts, submitDub, uploadEditVideo } from "../api/videos";
import { extractApiError } from "../utils/format";

export function useVideo() {
  const [loading, setLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState(null);

  async function submitUrl(url, shortsCount, subtitlesEnabled = true, generationMode = "smart", subtitleLanguage = "") {
    setLoading(true);
    setError(null);
    try {
      const { data } = await submitVideoUrl(url, Number(shortsCount), subtitlesEnabled, generationMode, subtitleLanguage);
      return data;
    } catch (e) {
      const msg = extractApiError(e);
      setError(msg);
      return null;
    } finally {
      setLoading(false);
    }
  }

  async function submitFile(file, shortsCount, subtitlesEnabled = true, generationMode = "smart", subtitleLanguage = "") {
    setLoading(true);
    setError(null);
    setUploadProgress(0);
    try {
      const { data } = await uploadVideoFile(file, Number(shortsCount), setUploadProgress, subtitlesEnabled, generationMode, subtitleLanguage);
      return data;
    } catch (e) {
      const msg = extractApiError(e);
      setError(msg);
      return null;
    } finally {
      setLoading(false);
    }
  }

  async function submitSubtitle(file, transcriptText, language = "") {
    setLoading(true);
    setError(null);
    setUploadProgress(0);
    try {
      const { data } = await uploadSubtitleVideo(file, transcriptText, language, setUploadProgress);
      return data;
    } catch (e) {
      const msg = extractApiError(e);
      setError(msg);
      return null;
    } finally {
      setLoading(false);
    }
  }

  async function submitTranscribe(file, language = "") {
    setLoading(true);
    setError(null);
    setUploadProgress(0);
    try {
      const { data } = await uploadTranscribeVideo(file, language, setUploadProgress);
      return data;
    } catch (e) {
      const msg = extractApiError(e);
      setError(msg);
      return null;
    } finally {
      setLoading(false);
    }
  }

  async function submitCleanup(file) {
    setLoading(true);
    setError(null);
    setUploadProgress(0);
    try {
      const { data } = await uploadCleanupMedia(file, setUploadProgress);
      return data;
    } catch (e) {
      const msg = extractApiError(e);
      setError(msg);
      return null;
    } finally {
      setLoading(false);
    }
  }

  async function submitSeparate(file) {
    setLoading(true);
    setError(null);
    setUploadProgress(0);
    try {
      const { data } = await uploadSeparateMedia(file, setUploadProgress);
      return data;
    } catch (e) {
      const msg = extractApiError(e);
      setError(msg);
      return null;
    } finally {
      setLoading(false);
    }
  }

  async function submitSpeech(text, opts = {}) {
    setLoading(true);
    setError(null);
    setUploadProgress(0);
    try {
      const { data } = await submitTts(text, opts, setUploadProgress);
      return data;
    } catch (e) {
      const msg = extractApiError(e);
      setError(msg);
      return null;
    } finally {
      setLoading(false);
    }
  }

  async function submitDubbing(file, opts = {}) {
    setLoading(true);
    setError(null);
    setUploadProgress(0);
    try {
      const { data } = await submitDub(file, opts, setUploadProgress);
      return data;
    } catch (e) {
      const msg = extractApiError(e);
      setError(msg);
      return null;
    } finally {
      setLoading(false);
    }
  }

  async function submitEditing(file, opts = {}) {
    setLoading(true);
    setError(null);
    setUploadProgress(0);
    try {
      const { data } = await uploadEditVideo(file, opts, setUploadProgress);
      return data;
    } catch (e) {
      const msg = extractApiError(e);
      setError(msg);
      return null;
    } finally {
      setLoading(false);
    }
  }

  return { submitUrl, submitFile, submitSubtitle, submitTranscribe, submitCleanup, submitSeparate, submitSpeech, submitDubbing, submitEditing, loading, uploadProgress, error };
}
