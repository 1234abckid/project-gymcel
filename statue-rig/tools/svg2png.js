// Render SVG files to PNG with headless Chromium (for QA and thumbnails).
// usage: node tools/svg2png.js out.png bgcolor file1.svg [file2.svg ...]   (tiles horizontally)
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const [out, bg, ...files] = process.argv.slice(2);
  const imgs = files.map(f => `<div style="display:inline-block;height:560px;margin:6px">${fs.readFileSync(f, 'utf8').replace(/width="\d+" height="\d+"/, 'style="height:560px;width:auto"')}</div>`).join('');
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1600, height: 580 }, deviceScaleFactor: 1 });
  await p.setContent(`<body style="margin:0;background:${bg};white-space:nowrap">${imgs}</body>`);
  await p.screenshot({ path: out, fullPage: true });
  await b.close();
})();
