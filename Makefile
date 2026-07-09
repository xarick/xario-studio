# Ildiz Makefile — butun stackni bitta buyruq bilan boshqarish.
#
# Og'ir joblar (TTS, video, rasm) Redis navbatiga tashlanadi va ularni ALOHIDA
# Celery worker bajaradi. Workersiz job "pending / 0%" holatida abadiy osilib
# qoladi — shuning uchun quruq `make` uchalasini birga ko'taradi.

.PHONY: help install dev api worker web check test build kill clean
.DEFAULT_GOAL := dev
.ONESHELL:
SHELL := /bin/bash

BACKEND   := backend
FRONTEND  := frontend
SUB       := $(MAKE) --no-print-directory -C

REDIS_HOST ?= localhost
REDIS_PORT ?= 6379
PG_HOST    ?= localhost
PG_PORT    ?= 5432

help:              ## Ko'rsatmalar
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'

install:           ## Backend + frontend bog'liqliklarini o'rnatish
	$(SUB) $(BACKEND) install && $(SUB) $(FRONTEND) install

check:             ## Redis, PostgreSQL va bog'liqliklar joyidami — tekshirish
	@ok=1
	if timeout 1 bash -c "</dev/tcp/$(REDIS_HOST)/$(REDIS_PORT)" 2>/dev/null; then
	  echo "✓ Redis        $(REDIS_HOST):$(REDIS_PORT)"
	else
	  echo "✗ Redis        $(REDIS_HOST):$(REDIS_PORT) javob bermayapti"
	  echo "               docker run -d -p 6379:6379 --name xario-redis redis:7-alpine"
	  ok=0
	fi
	if timeout 1 bash -c "</dev/tcp/$(PG_HOST)/$(PG_PORT)" 2>/dev/null; then
	  echo "✓ PostgreSQL   $(PG_HOST):$(PG_PORT)"
	else
	  echo "✗ PostgreSQL   $(PG_HOST):$(PG_PORT) javob bermayapti"
	  ok=0
	fi
	if [ -d "$(BACKEND)/.venv" ]; then
	  echo "✓ backend/.venv"
	else
	  echo "✗ backend/.venv yo'q — 'make install' ishga tushiring"
	  ok=0
	fi
	if [ -d "$(FRONTEND)/node_modules" ]; then
	  echo "✓ frontend/node_modules"
	else
	  echo "✗ frontend/node_modules yo'q — 'make install' ishga tushiring"
	  ok=0
	fi
	if [ "$$ok" != 1 ]; then
	  echo
	  echo "Yuqoridagilarni to'g'rilab, qaytadan urinib ko'ring."
	  exit 1
	fi

# Uchala jarayon parallel ishlaydi. `set -m` har bir background jobga alohida
# process group beradi, shuning uchun `kill -TERM -$pid` uvicorn/celery/vite ning
# bola processlarini ham qo'shib o'ldiradi — Ctrl+C dan keyin osilib qolgan port
# qolmaydi. stdin /dev/null ga ulanadi: aks holda vite tugma bosishini kutib
# SIGTTIN dan to'xtab qoladi.
dev: check         ## Backend + worker + frontend birga — quruq `make` ham shu (Ctrl+C hammasini to'xtatadi)
	@echo
	echo "→ api      http://localhost:8000  (docs: /docs)"
	echo "→ web      http://localhost:5173"
	echo "→ worker   Celery — og'ir joblar"
	echo
	set -m
	pids=()
	cleanup() {
	  trap - INT TERM EXIT
	  echo
	  echo "→ To'xtatilmoqda…"
	  for p in "$${pids[@]}"; do kill -TERM -"$$p" 2>/dev/null || true; done
	  # Celery warm-shutdown ~3s oladi. Guruhlar o'lgunicha 10s kutamiz —
	  # aks holda prompt qaytgach worker hali tirik qolib, darrov qayta
	  # ishga tushirilsa ikkita worker ustma-ust tushadi.
	  for _ in {1..50}; do
	    alive=0
	    for p in "$${pids[@]}"; do kill -0 -"$$p" 2>/dev/null && alive=1; done
	    [ "$$alive" -eq 0 ] && break
	    sleep 0.2
	  done
	  # Osilib qolgani bo'lsa — majburan.
	  for p in "$${pids[@]}"; do kill -KILL -"$$p" 2>/dev/null || true; done
	  wait 2>/dev/null || true
	  exit 0
	}
	trap cleanup INT TERM EXIT
	( $(SUB) $(BACKEND)  dev    </dev/null 2>&1 | sed -u "s/^/[api]    /" ) & pids+=($$!)
	( $(SUB) $(BACKEND)  worker </dev/null 2>&1 | sed -u "s/^/[worker] /" ) & pids+=($$!)
	( $(SUB) $(FRONTEND) dev    </dev/null 2>&1 | sed -u "s/^/[web]    /" ) & pids+=($$!)
	wait -n
	echo
	echo "→ Jarayonlardan biri to'xtadi — qolganlari ham to'xtatiladi."

api:               ## Faqat API serveri
	$(SUB) $(BACKEND) dev

worker:            ## Faqat Celery worker
	$(SUB) $(BACKEND) worker

web:               ## Faqat frontend dev serveri
	$(SUB) $(FRONTEND) dev

test:              ## Backend testlari
	$(SUB) $(BACKEND) test

build:             ## Frontend production build
	$(SUB) $(FRONTEND) build

kill:              ## 8000 va 5173 portlarini bo'shatish + qolgan workerlarni o'ldirish
	-$(SUB) $(BACKEND) kill
	-@lsof -ti:5173 | xargs -r kill -9 2>/dev/null && echo "Port 5173 bo'shatildi" || echo "Port 5173 allaqachon bo'sh"
	-@pkill -f 'celery -A app.core.celery_app' 2>/dev/null && echo "Celery workerlar to'xtatildi" || echo "Ishlayotgan Celery worker yo'q"
