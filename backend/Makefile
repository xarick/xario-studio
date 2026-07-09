.PHONY: help install install-gpu dev worker worker-media worker-heavy kill migrate downgrade revision history current shell test

help:              ## Ko'rsatmalar
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'

install:           ## Bog'liqliklarni o'rnatish
	uv sync

install-gpu:       ## GPU (CUDA) bilan — faster-whisper GPU transkripsiya uchun
	uv sync --extra gpu

dev:               ## API serverni ishga tushirish — http://localhost:8000
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:            ## Celery worker — ikkala navbatni ham eshitadi (Redis kerak)
	uv run celery -A app.core.celery_app:celery_app worker -Q media,heavy --loglevel=info

worker-media:      ## Faqat yengil navbat (ffmpeg) — og'ir joblar bloklamaydi
	uv run celery -A app.core.celery_app:celery_app worker -Q media --loglevel=info

worker-heavy:      ## Faqat og'ir navbat (whisper / XTTS / Demucs)
	uv run celery -A app.core.celery_app:celery_app worker -Q heavy --loglevel=info

test:              ## Testlarni ishga tushirish
	uv run pytest -q

kill:              ## 8000-portdagi processni o'ldirish
	@lsof -ti:8000 | xargs kill -9 2>/dev/null && echo "Port 8000 bo'shatildi" || echo "Port 8000 allaqachon bo'sh"

migrate:           ## Barcha migratsiyalarni qo'llash
	uv run alembic upgrade head

downgrade:         ## Oxirgi migratsiyani bekor qilish
	uv run alembic downgrade -1

revision:          ## Yangi migratsiya: make revision msg="nima o'zgardi"
	uv run alembic revision --autogenerate -m "$(msg)"

history:           ## Migratsiya tarixini ko'rish
	uv run alembic history

current:           ## Joriy migratsiya versiyasi
	uv run alembic current

shell:             ## Python shell
	uv run python
