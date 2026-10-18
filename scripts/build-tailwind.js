#!/usr/bin/env node
// build-tailwind.js — Standalone Tailwind CSS build for Odysseus
// Usage: node scripts/build-tailwind.js
const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const ROOT = path.resolve(__dirname, '..');
const INPUT = path.join(ROOT, 'static', 'tailwind.css');
const OUTPUT = path.join(ROOT, 'static', 'css', 'style.tailwind.min.css');

// Check if tailwindcss is installed
try {
  require.resolve('tailwindcss');
} catch {
  console.log('[A5] Installing tailwindcss@3...');
  execSync('npm install --save-dev tailwindcss@3', { cwd: ROOT, stdio: 'inherit' });
}

console.log('[A5] Building Tailwind CSS...');
execSync(
  `npx tailwindcss -i "${INPUT}" -o "${OUTPUT}" --minify`,
  { cwd: ROOT, stdio: 'inherit' }
);

const stats = fs.statSync(OUTPUT);
const kb = (stats.size / 1024).toFixed(1);
console.log(`[A5] ✅ Output: ${OUTPUT}`);
console.log(`[A5] Size: ${stats.size} bytes (${kb} KB)`);
if (stats.size > 200 * 1024) {
  console.error(`[A5] ⚠️  Over 200 KB target! Current: ${kb} KB`);
  process.exit(1);
} else {
  console.log(`[A5] ✅ Under 200 KB target`);
}
