from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import logging

logger = logging.getLogger(__name__)

_DEFAULT_SECRET = "insecure-dev-secret-key"
_DEFAULT_ADMIN_PASSWORD = "Admin123!"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    DEBUG: bool = True
    SECRET_KEY: str = _DEFAULT_SECRET
    FRONTEND_URL: str = "http://localhost:5173"

    # Auth
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    # Brute-force throttle on /auth/login: max attempts per IP per window.
    LOGIN_RATE_MAX_ATTEMPTS: int = 10
    LOGIN_RATE_WINDOW_SEC: int = 300

    # Super admin seed (used in migration 0003)
    SUPER_ADMIN_USERNAME: str = "admin"
    SUPER_ADMIN_PASSWORD: str = _DEFAULT_ADMIN_PASSWORD

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/xario_db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30

    # Storage
    UPLOAD_DIR: str = "storage/uploads"
    OUTPUT_DIR: str = "storage/outputs"
    # Disk hygiene: aged, unreferenced uploads + orphaned output dirs are swept.
    FILE_RETENTION_DAYS: int = 7
    CLEANUP_ON_STARTUP: bool = True

    # Background job queue (Celery + Redis)
    # Heavy ML jobs (transcribe, separate, tts, dub, …) run in a separate worker
    # process so they never block the web API. The worker is started with
    # `make worker` (or its own container in docker-compose).
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    # Two lanes so a one-hour dub can't block a five-second GIF. `make worker`
    # drains both; in production run one worker per queue (see workers/queues.py).
    CELERY_QUEUE_MEDIA: str = "media"
    CELERY_QUEUE_HEAVY: str = "heavy"
    # One heavy job at a time per worker — the ML models are memory/GPU-bound and
    # don't parallelise well on a single host. Scale by adding worker containers.
    WORKER_CONCURRENCY: int = 1
    # Dev escape hatch: run jobs inline in the web process (no Redis/worker
    # needed). Mirrors the old BackgroundTasks behaviour for quick local testing.
    CELERY_TASK_ALWAYS_EAGER: bool = False

    # Processing limits
    MIN_SHORT_DURATION: int = 30   # seconds — hard floor / validation
    MAX_SHORT_DURATION: int = 60   # seconds — each short max 1 minute
    SIMPLE_MIN_DURATION: int = 45  # seconds — simple shorts vary between this and MAX
    MAX_SHORTS_COUNT: int = 10
    MAX_UPLOAD_SIZE_MB: int = 500

    # ffmpeg watchdog — catches a wedged encoder, it is not a quality-of-service
    # deadline. A fixed cap kills long jobs that are progressing fine, so the
    # budget scales with the media the command must chew through:
    #   max(MIN, work_seconds * FACTOR)
    # `work_seconds` is the source duration for whole-file ops and the clip
    # length for cuts. FACTOR=6 allows an encode running 6× slower than realtime.
    FFMPEG_MIN_TIMEOUT: int = 600
    FFMPEG_TIMEOUT_FACTOR: float = 6.0

    # Smart highlight generation (mode = "smart")
    # Each short = a compilation of non-contiguous "highlight" clips picked from
    # scene changes + speech-dense moments. Multiple variations are generated so
    # the user can pick the best one.
    SCENE_DETECT_THRESHOLD: float = 0.27   # 0–1; lower = more scene cuts detected
    SMART_CLIP_MIN: int = 5                 # seconds — shortest highlight clip
    SMART_CLIP_MAX: int = 12                # seconds — longest highlight clip

    # Subtitles
    # Style: "karaoke" (words light up in sync with speech) | "plain"
    SUBTITLE_STYLE: str = "karaoke"
    SUBTITLE_WORDS_PER_LINE: int = 4

    # Pro mode — auto-reframe (crop to 9:16) following on-screen activity / mouse
    REFRAME_SAMPLE_FPS: float = 6.0    # how often motion is sampled (frames/sec)
    REFRAME_SMOOTHING: float = 0.72    # EMA factor (higher = slower, smoother pan)

    # yt-dlp — cookies for YouTube bot-check bypass
    # YTDLP_COOKIES_FILE takes priority over YTDLP_COOKIES_FROM_BROWSER
    YTDLP_COOKIES_FILE: str = ""              # path to Netscape cookies.txt
    YTDLP_COOKIES_FROM_BROWSER: str = "chrome"  # fallback: chrome | firefox | ""

    # Whisper transcription (faster-whisper)
    # Model sizes: tiny | base | small | medium | large-v3
    # Device: cpu | cuda  (compute_type auto-set: int8 on cpu, float16 on cuda)
    WHISPER_MODEL_SIZE: str = "base"
    WHISPER_DEVICE: str = "cpu"          # cpu | cuda (auto-falls back to cpu if GPU unavailable)
    WHISPER_COMPUTE_TYPE: str = ""       # "" = auto (cpu→int8, cuda→int8_float16); or float16 / int8
    WHISPER_LANGUAGE: str = ""           # "" = auto-detect; or force e.g. "en", "ru", "uz"

    # Text-to-speech (Coqui XTTS-v2) — generation_mode = "tts"
    # Multilingual, offline, GPU-capable. Falls back to CPU automatically.
    # First run downloads the model (~1.8 GB); COQUI_TOS_AGREED is set for us.
    TTS_MODEL: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    TTS_DEVICE: str = "cuda"        # cuda | cpu (auto-falls back to cpu if GPU unavailable)
    TTS_DEFAULT_VOICE: str = "Ana Florence"   # a built-in XTTS studio speaker
    # XTTS has no native Uzbek voice. Uzbek (Latin) text is read using this
    # phonetically-closest supported language token (Turkish by default).
    TTS_UZBEK_PROXY_LANG: str = "tr"
    TTS_MAX_CHARS: int = 5000       # hard cap on input text length
    TTS_TIMEOUT: int = 1800         # seconds — synthesis can be slow on CPU

    # Translate + dub (generation_mode = "dub")
    # Each translated segment is time-stretched to fit the original segment's
    # timing; the stretch factor is clamped to keep the voice natural.
    DUB_MIN_TEMPO: float = 0.7      # slowest (longer) — below this we don't stretch further
    DUB_MAX_TEMPO: float = 1.6      # fastest (shorter) — caps "chipmunk" speed-ups
    DUB_REF_MAX_SECONDS: int = 30   # length of source-audio reference used for voice cloning

    # Image processing (background removal, …)
    IMAGE_TIMEOUT: int = 300        # seconds — per image operation

    # Image-to-shorts slideshow (operation = "image_to_shorts")
    SLIDESHOW_SECONDS_PER_IMAGE: float = 3.5   # how long each image is shown
    SLIDESHOW_TRANSITION: float = 0.6          # crossfade duration between images
    SLIDESHOW_MAX_IMAGES: int = 20             # hard cap on images per short

    # AI provider — change AI_PROVIDER in .env to switch (openai | ollama | gemini)
    AI_PROVIDER: str = "openai"
    AI_API_KEY: str = ""
    AI_MODEL: str = "gpt-4o-mini"
    AI_BASE_URL: str | None = None   # custom endpoint (Azure, proxy, etc.)

    @model_validator(mode="after")
    def _check_production_secrets(self) -> "Settings":
        """Refuse to boot a production instance on the values published in this
        repository. Migration 0003 seeds (and re-seeds) the superadmin with
        SUPER_ADMIN_PASSWORD, so leaving it at the default hands anyone who has
        read the source a working admin login."""
        if not self.DEBUG:
            if self.SECRET_KEY == _DEFAULT_SECRET:
                raise ValueError("Set SECRET_KEY in .env before deploying to production.")
            if self.SUPER_ADMIN_PASSWORD == _DEFAULT_ADMIN_PASSWORD:
                raise ValueError(
                    "Set SUPER_ADMIN_PASSWORD in .env — the default is public in the repo."
                )
        else:
            if self.SECRET_KEY == _DEFAULT_SECRET:
                logger.warning("Using insecure default SECRET_KEY. Change it before deploying.")
            if self.SUPER_ADMIN_PASSWORD == _DEFAULT_ADMIN_PASSWORD:
                logger.warning("Using the default SUPER_ADMIN_PASSWORD. Change it before deploying.")
        return self


settings = Settings()
