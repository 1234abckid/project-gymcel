#!/usr/bin/env node
/*
 * Render a scene JSON to MP4 (or a single PNG still) with headless Chromium + ffmpeg.
 *
 *   node tools/render.js scenes/demo.json out/demo.mp4
 *   node tools/render.js scenes/demo.json out/thumb.png --still 2.5
 *   options: --fps 30  --from 0 --to 5  --scale 0.5 (fast low-res preview)  --crf 18
 *
 * Frames are produced by calling anim.renderAt(t) for exact times, so output is
 * deterministic and independent of machine speed.  If the scene has "audio"
 * (path relative to the scene file) it is muxed in.
 */
const { chromium } = require('playwright');
const http = require('http');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.css': 'text/css', '.woff2': 'font/woff2', '.svg': 'image/svg+xml', '.png': 'image/png', '.mp3': 'audio/mpeg', '.wav': 'audio/wav' };

function serve() {
  return new Promise(res => {
    const srv = http.createServer((req, r) => {
      const p = path.join(ROOT, decodeURIComponent(new URL(req.url, 'http://x').pathname));
      if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { r.writeHead(404); return r.end(); }
      r.writeHead(200, { 'Content-Type': MIME[path.extname(p)] || 'application/octet-stream' });
      fs.createReadStream(p).pipe(r);
    }).listen(0, '127.0.0.1', () => res(srv));
  });
}

function arg(name, dflt) { const i = process.argv.indexOf('--' + name); return i > 0 ? process.argv[i + 1] : dflt; }

(async () => {
  const [sceneArg, outArg] = process.argv.slice(2).filter((a, i, all) => !a.startsWith('--') && !(all[i - 1] || '').startsWith('--'));
  if (!sceneArg || !outArg) { console.error('usage: node tools/render.js <scene.json> <out.mp4|out.png> [--still t] [--fps n] [--from s] [--to s] [--scale k] [--crf n]'); process.exit(1); }
  const scenePath = path.resolve(sceneArg), out = path.resolve(outArg);
  const scene = JSON.parse(fs.readFileSync(scenePath, 'utf8'));
  const scale = parseFloat(arg('scale', '1'));
  const W = scene.width || 1920, H = scene.height || 1080;
  const fps = parseFloat(arg('fps', scene.fps || 30));
  const from = parseFloat(arg('from', '0')), to = parseFloat(arg('to', scene.duration));
  fs.mkdirSync(path.dirname(out), { recursive: true });

  const srv = await serve();
  const url = `http://127.0.0.1:${srv.address().port}/engine/player.html?render=1&scene=${encodeURIComponent('/' + path.relative(ROOT, scenePath).split(path.sep).join('/'))}`;
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: scale });
  page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') console.error('[page]', m.text()); });
  page.on('pageerror', e => console.error('[page error]', e.message));
  await page.goto(url);
  await page.waitForFunction('window.READY === true', null, { timeout: 60000 });

  const still = arg('still');
  if (still !== undefined) {
    await page.evaluate(t => window.anim.renderAt(t), parseFloat(still));
    await page.screenshot({ path: out, type: out.endsWith('.jpg') ? 'jpeg' : 'png' });
    console.log('wrote', out);
    await browser.close(); srv.close(); return;
  }

  const audio = scene.audio ? path.resolve(path.dirname(scenePath), scene.audio) : null;
  const ffArgs = ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-'];
  if (audio && fs.existsSync(audio)) ffArgs.push('-ss', String(from), '-i', audio, '-c:a', 'aac', '-b:a', '192k', '-shortest');
  ffArgs.push('-c:v', 'libx264', '-preset', 'medium', '-crf', arg('crf', '18'), '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out);
  const ff = spawn('ffmpeg', ffArgs, { stdio: ['pipe', 'inherit', 'inherit'] });
  const n = Math.round((to - from) * fps);
  const t0 = Date.now();
  for (let i = 0; i < n; i++) {
    const t = from + i / fps;
    await page.evaluate(tt => window.anim.renderAt(tt), t);
    const buf = await page.screenshot({ type: 'jpeg', quality: 93 });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (i % fps === 0) process.stdout.write(`\rframe ${i}/${n}  (${((Date.now() - t0) / 1000).toFixed(1)} s)`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
  console.log(`\nwrote ${out}  (${n} frames, ${((Date.now() - t0) / 1000).toFixed(1)} s)`);
  await browser.close(); srv.close();
})().catch(e => { console.error(e); process.exit(1); });
