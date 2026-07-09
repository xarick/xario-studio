import enum


class UserRole(str, enum.Enum):
    superadmin = "superadmin"
    admin = "admin"
    user = "user"


class VideoSourceType(str, enum.Enum):
    upload = "upload"
    url = "url"


class GenerationMode(str, enum.Enum):
    """How shorts are cut from the source video.

    simple — each short is ONE contiguous segment; the shorts are spread
             evenly across the video. Fast and predictable.
    smart  — each short is a compilation of non-contiguous "highlight" clips
             (scene changes + speech-dense moments). Several variations are
             produced so the user can pick the best one.
    pro    — like smart for clip selection, but reframes (crops) the footage to
             9:16 following on-screen activity / the mouse cursor instead of
             using blurred letterbox bars. Best for screen / monitor recordings.
    subtitle — no splitting/cropping: the user supplies the exact transcript and
             we force-align it to the audio, then burn subtitles onto the WHOLE
             video at its original size. For any video, not just shorts.
    transcribe — speech-to-text: transcribe an audio OR video file into timed
             segments; no media output, the result is a downloadable transcript.
    cleanup — audio cleanup: loudness normalisation + denoise (+ silence trim for
             audio-only). Works on audio or video (video stream is kept as-is).
    separate — vocal/music separation (Demucs): split into vocals + instrumental;
             for video also produces a karaoke (instrumental) video.
    tts    — text-to-speech: no input media; the user supplies text + a language
             and (optionally) a reference voice, and an audio clip is synthesised
             with Coqui XTTS-v2. The result is a downloadable audio file.
    dub    — translate + dub: whisper transcribes the source, an LLM translates
             each segment to the target language, XTTS re-voices it (cloning the
             original speaker by default), and the new audio is time-fit to the
             original timing and muxed back. Output: dubbed video (or audio).
    edit   — manual montage: trim a chosen [start, end] region, fit it to a target
             aspect (9:16 / 1:1 / 16:9 / original) by center-crop or blurred pad,
             and optionally burn a static text overlay. Params live in params_json.
             Output: one edited video Short.
    tool   — single-purpose media tool (ffmpeg). The concrete operation + args are
             in params_json["op"] (compress / speed / gif / extract_audio / aspect
             for video; trim / convert / volume / pitch for audio). Output: one Short.
    """
    simple = "simple"
    smart = "smart"
    pro = "pro"
    subtitle = "subtitle"
    transcribe = "transcribe"
    cleanup = "cleanup"
    separate = "separate"
    tts = "tts"
    dub = "dub"
    edit = "edit"
    tool = "tool"


class VideoStatus(str, enum.Enum):
    pending = "pending"
    downloading = "downloading"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class ShortStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class NotificationType(str, enum.Enum):
    job_completed = "job_completed"
    job_failed = "job_failed"


class ImageStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class ImageOperation(str, enum.Enum):
    """What to do in an image job.

    bg_remove      — remove the background, returning a transparent PNG (rembg/u2net).
    image_to_shorts — animate one or more uploaded images into a 9:16 short
                     (ken-burns zoom + crossfades). The result is a downloadable MP4.
    """
    bg_remove = "bg_remove"
    image_to_shorts = "image_to_shorts"
    crop = "crop"        # center-crop to an aspect ratio
    resize = "resize"    # scale to a target width (keeps ratio)
    convert = "convert"  # change file format (png/jpg/webp)
    enhance = "enhance"  # sharpen + contrast/colour boost
    upscale = "upscale"  # enlarge 2×/4× (Lanczos)
