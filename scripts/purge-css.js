const { PurgeCSS } = require('purgecss');
const fs = require('fs');
const path = require('path');

const BASE = path.resolve(__dirname, '..');

async function main() {
    const purgeCSSResult = await new PurgeCSS().purge({
        content: [
            `${BASE}/static/index.html`,
            `${BASE}/static/login.html`,
            `${BASE}/static/js/**/*.js`,
        ],
        css: [`${BASE}/static/css/style.min.css`],
        safelist: {
            standard: [/^hljs/, /^cm-/, /^CodeMirror/, /^mermaid/, /^katex/],
            deep: [/tooltip/, /modal/, /toast/, /sidebar/, /panel/, /dropdown/],
            greedy: [/^data-/, /^aria-/],
        },
        rejected: true,
    });

    for (const result of purgeCSSResult) {
        const outPath = path.join(BASE, 'static/css/style.purged.css');
        fs.writeFileSync(outPath, result.css);
        const origSize = fs.statSync(path.join(BASE, 'static/css/style.min.css')).size;
        const newSize = Buffer.byteLength(result.css);
        const reduction = ((1 - newSize / origSize) * 100).toFixed(1);
        console.log(`Purged: ${(origSize/1024).toFixed(0)} KB → ${(newSize/1024).toFixed(0)} KB (${reduction}% reduction)`);

        if (result.rejected && result.rejected.length > 0) {
            const rejectedPath = path.join(BASE, 'static/css/style.rejected.json');
            fs.writeFileSync(rejectedPath, JSON.stringify(result.rejected, null, 2));
            console.log(`Rejected selectors saved to style.rejected.json (${result.rejected.length} rules)`);
        }
    }
}

main().catch(err => { console.error(err); process.exit(1); });
