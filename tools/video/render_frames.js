// node render_frames.js <timeline.json> <model.json|-> <frames_dir> [workers]
// Покадровый рендер: страница scene.html, функция drawAt(t) детерминирована; скриншот каждого кадра (Playwright, Chromium).
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
(async () => {
  const [tlp, mp, outDir, nw = '4'] = process.argv.slice(2);
  const TL = JSON.parse(fs.readFileSync(tlp, 'utf8')), MODEL = mp !== '-' ? JSON.parse(fs.readFileSync(mp, 'utf8')) : null;
  fs.mkdirSync(outDir, { recursive: true });
  const N = Math.round(TL.duration * TL.fps), W = TL.canvas.width, H = TL.canvas.height, workers = +nw;
  const AT = process.env.AT ? process.env.AT.split(',').map(Number) : null;
  const browser = await chromium.launch();
  const html = 'file://' + path.resolve(__dirname, 'scene.html');
  await Promise.all([...Array(workers).keys()].map(async w => {
    const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
    page.on('pageerror', e => { console.error('PAGEERROR', e.message); process.exitCode = 4; });
    await page.goto(html);
    await page.evaluate(({ TL, MODEL }) => { window.TL = TL; window.MODEL = MODEL; window.initScene(); }, { TL, MODEL });
    if (AT) { for (const t of AT) { await page.evaluate(t => window.drawAt(t), t); await page.screenshot({ path: path.join(outDir, `at_${t}.png`) }); } await page.close(); return; }
    for (let i = w; i < N; i += workers) {
      await page.evaluate(t => window.drawAt(t), i / TL.fps);
      await page.screenshot({ path: path.join(outDir, `f${String(i).padStart(5, '0')}.png`), type: 'png' });
    }
    await page.close();
  }));
  await browser.close(); console.log('frames', N);
})();
