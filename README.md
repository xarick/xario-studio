# xario-studio

A self-hosted **AI media studio** — an admin panel that turns long videos into
short clips and bundles a suite of video, audio and image tools around it.
FastAPI + PostgreSQL backend, React + Vite + Tailwind frontend, heavy ML jobs
run on a Celery/Redis worker (GPU-accelerated when available, with automatic CPU
fallback).

## Features

**Video**
- **Shorts** — `simple` (contiguous 45–60 s clips), `smart` (scene + speech
  highlight compilations, several variations) and `pro` (auto-reframe to 9:16
  following the speaker / mouse).
- **Editor** — manual razor-cut montage: trim, join, aspect-fit, timed captions.
- **Merge** — join several clips with `xfade` transitions, optional background music.
- **Subtitles** — burn your exact transcript onto a video (forced alignment).
- **Cleanup / Separate / Dub / Transcribe** — see Audio.

**Audio**
- **Text → Speech** (Coqui XTTS-v2, multilingual, optional voice cloning).
- **Transcribe** (faster-whisper → TXT / SRT / VTT).
- **Cleanup** (denoise + EBU R128 loudness normalisation).
- **Separate** (Demucs vocal / instrumental split, optional karaoke video).
- **Dub** (whisper → LLM translate → re-voice → mux).
- **Merge** (concatenate, or mix voice + ducked music).

**Image**
- Background removal (rembg/u2net), images → 9:16 slideshow, and tools:
  crop, resize, convert, enhance, upscale.

**Platform**
- JWT auth with `user` / `admin` / `superadmin` roles; per-user resource
  ownership (a superadmin sees everything).
- Login rate-limiting, aged-file cleanup, stuck-job reconciliation.
- i18n: Uzbek, Russian, English.

## Tech stack

| Layer      | Tech                                                                  |
|------------|----------------------------------------------------------------------|
| Backend    | FastAPI, SQLAlchemy 2, Alembic, Celery + Redis, uv                    |
| ML / media | ffmpeg, faster-whisper, Coqui XTTS-v2, Demucs, OpenCV, rembg, yt-dlp  |
| Frontend   | React 18, Vite 5, Tailwind 4, react-router, i18next                   |
| Data       | PostgreSQL                                                            |

## Architecture

```
backend/src/app/
  api/v1/     HTTP layer (endpoints + dependencies)
  core/       config, security, uploads, rate-limit
  db/         models, enums, session  (migrations live in backend/alembic)
  modules/    per-domain repository + service + schemas (videos, shorts, images, auth)
  workers/    Celery tasks + the media pipeline (video_processor, ffmpeg, …)
frontend/src/
  api/  components/  contexts/  hooks/  pages/  locales/  config/
devops/       docker-compose + nginx reverse proxy
```

New single-output video modes register a handler in
`workers/video_processor._SPECIAL_MODES`; image operations register in
`workers/image_processor._OPERATIONS`; frontend tools are schema-driven in
`frontend/src/config/tools.js`.

## Prerequisites

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Node 20+
- PostgreSQL 14+
- Redis (for the job queue)
- ffmpeg on `PATH`
- Optional: an NVIDIA GPU + CUDA for faster whisper / TTS / Demucs

## Setup

```bash
# Backend
cd backend
cp .env.example .env          # then edit SECRET_KEY, DATABASE_URL, AI_* …
make install                  # uv sync   (use `make install-gpu` for CUDA extras)
make migrate                  # apply Alembic migrations

# Frontend
cd ../frontend
make install                  # npm install
```

## Running (development)

```bash
make                          # api + worker + frontend, Ctrl+C stops all three
```

Or one process at a time:

```bash
# Redis must be running (e.g. `redis-server`, or the docker-compose service)
cd backend  && make dev       # API  → http://localhost:8000  (docs at /docs)
cd backend  && make worker    # Celery worker, drains both queues
cd frontend && make dev       # UI   → http://localhost:5173
```

Set `CELERY_TASK_ALWAYS_EAGER=true` in `.env` to run jobs inline without a
worker/Redis (handy for quick local testing).

There is no public sign-up. Migration `0003` seeds a superadmin from
`SUPER_ADMIN_USERNAME` / `SUPER_ADMIN_PASSWORD` the first time you migrate a
database, and that account creates everyone else from the Users page. Set the
password in `.env` **before** that first `alembic upgrade` — afterwards the
migration will not run again, and the password can only be changed from the app.
With `DEBUG=false` the app refuses to start on the default value.

### Two queues

Jobs are routed by cost when they are submitted (`workers/queues.py`): `heavy`
for anything that loads whisper / XTTS / Demucs, `media` for plain ffmpeg
transforms. A one-hour dub therefore cannot block a five-second GIF. `make
worker` drains both; `make worker-media` and `make worker-heavy` run one lane
each.

## Testing

```bash
cd backend  && make test      # pytest (SQLite, in-process queue)
cd frontend && npm run build  # bundle check
```

CI runs both on every push to `main` and every PR (`.github/workflows/ci.yml`).

## Deployment

`devops/docker-compose.yml` brings up the backend, frontend, PostgreSQL, Redis,
one worker per queue and an nginx reverse proxy. Scale a lane on its own with
`docker compose up -d --scale worker-media=3`.

Three values have no safe default and must be set before the first run:

| Variable | Where | Why |
| --- | --- | --- |
| `SECRET_KEY` | `backend/.env` | signs the JWTs; the app refuses to start on the default when `DEBUG=false` |
| `SUPER_ADMIN_PASSWORD` | `backend/.env` | migration `0003` seeds the superadmin with it on the first migration, and the default is public in this repo |
| `POSTGRES_PASSWORD` | compose environment | compose refuses to start without it |

The database publishes no host port — only the backend and the workers reach it,
over the compose network.

## License

See [LICENSE](LICENSE).
