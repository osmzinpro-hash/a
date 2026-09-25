// Downloads every file listed in media/manifest.json that is not in the repo yet.
// Runs inside GitHub Actions (see .github/workflows/media-sync.yml), where the
// Higgsfield CDN is reachable. Existing files are never re-downloaded.
import { readFile, writeFile, mkdir, access } from 'node:fs/promises';
import { dirname } from 'node:path';

const manifest = JSON.parse(await readFile(new URL('./manifest.json', import.meta.url), 'utf8'));
let failed = 0;

for (const { url, path } of manifest.files) {
  try {
    await access(path);
    console.log(`skip  ${path}`);
    continue;
  } catch {}
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const buf = Buffer.from(await res.arrayBuffer());
    await mkdir(dirname(path), { recursive: true });
    await writeFile(path, buf);
    console.log(`got   ${path} (${(buf.length / 1024).toFixed(0)} KB)`);
  } catch (err) {
    failed++;
    console.error(`FAIL  ${path}: ${err.message}`);
  }
}

if (failed) process.exitCode = 1;
