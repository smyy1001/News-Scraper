#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "=== IHA SCRAPER ==="
mkdir -p iha_output
docker build -t iha-scraper iha/
docker run --rm \
  -v "$(pwd)/iha_output:/app/output" \
  iha-scraper

echo "=== DHA SCRAPER ==="
mkdir -p dha_output
docker build -t dha-scraper dha/
docker run --rm \
  -v "$(pwd)/dha_output:/app/output" \
  dha-scraper

echo "✅ All done."
