@echo off
REM Build Tailwind CSS for Odysseus
REM Run this from the project root: scripts\build-tailwind.bat

echo [A5] Installing Tailwind CSS...
call npm install --save-dev tailwindcss@3

echo [A5] Building Tailwind CSS...
call npx tailwindcss -i static/tailwind.css -o static/css/style.tailwind.min.css --minify

echo [A5] Done. Output: static/css/style.tailwind.min.css
dir static\css\style.tailwind.min.css
