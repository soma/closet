DELAY ?= 3

.PHONY: help setup fetch merge build backfill-imdb posters poster-status summary update refresh test

help:
	@echo "make setup    one-time: venv, playwright, chromium (only needed for tests)"
	@echo "make fetch    (DELAY=10 to go slower) find visits missing from the dataset, write new.json (run from your machine)"
	@echo "make merge    validate and merge new.json into data/closet.json"
	@echo "make build    regenerate index.html and dist/index.html"
	@echo "make backfill-imdb  fill blank imdb_id values from Wikidata (slow: it obeys Wikidata's rate limit)"
	@echo "make posters  download posters and pack the sprite sheets (.cache/posters/sheets) for the Pages app"
	@echo "make update  fetch + merge + imdb ids + posters + build + test + summary (run on your machine)"
	@echo "make poster-status  which poster sheets still need uploading to the Pages app"
	@echo "make refresh  fetch + merge + build + test"
	@echo "make test     run script/test"

setup:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt
	.venv/bin/playwright install chromium

fetch:
	python3 scripts/fetch_letterboxd.py --out new.json --delay $(DELAY)

merge:
	@test -f new.json || { echo "new.json not found: run make fetch first"; exit 1; }
	python3 scripts/merge_data.py new.json

build:
	python3 scripts/build.py

posters:
	.venv/bin/python scripts/make_posters.py

backfill-imdb:
	cd scripts && python3 backfill_imdb.py --delay 62

poster-status:
	python3 scripts/poster_status.py

summary:
	python3 scripts/update_summary.py

update: fetch merge backfill-imdb posters build test summary

refresh: fetch merge build test

test:
	script/test
