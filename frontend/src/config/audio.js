/**
 * Audio module constants shared by the TTS and dub pages.
 *
 * VOICES and TTS_MAX_CHARS mirror the backend: `workers/tts.py` BUILTIN_VOICES
 * and `settings.TTS_MAX_CHARS`. Keep them in step — the backend rejects an
 * unknown voice by falling back to its default, and over-long text with a 400.
 */

/** Languages offered in the pickers. `uz` is read through a Turkish proxy. */
export const LANGUAGES = ["uz", "ru", "en", "tr", "de", "es", "fr", "it", "pt", "ar"];

/** Built-in XTTS-v2 studio speakers. */
export const VOICES = [
  "Ana Florence", "Claribel Dervla", "Alison Dietlinde", "Sofia Hellen",
  "Tammie Ema", "Asya Anara", "Daisy Studious",
  "Andrew Chipper", "Damien Black", "Viktor Eka", "Craig Gutsy",
  "Eugenio Mataracı", "Ilkin Urumov", "Badr Odhiambo",
];

export const TTS_MAX_CHARS = 5000;
