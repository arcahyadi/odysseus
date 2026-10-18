#!/usr/bin/env bash
# Build Tailwind CSS for Odysseus
# Run from project root: bash scripts/build-tailwind.sh
set -euo pipefail

echo "[A5] Installing Tailwind CSS..."
npm install --save-dev tailwindcss@3

echo "[A5] Building Tailwind CSS..."
npx tailwindcss -i static/tailwind.css -o static/css/style.tailwind.min.css --minify

SIZE=$(wc -c < static/css/style.tailwind.min.css | tr -d ' ')
echo "[A5] Done. Output: static/css/style.tailwind.min.css (${SIZE} bytes)"
