.PHONY: help install dev build preview

help:              ## Ko'rsatmalar
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'

install:           ## npm paketlarini o'rnatish
	npm install

dev:               ## Dev serverni ishga tushirish — http://localhost:5173
	npm run dev

build:             ## Production build
	npm run build

preview:           ## Build natijasini ko'rish
	npm run preview
