// Рендер ролика: node render.js <page.html> <build_dir> <out.mp4> [--stills t1,t2,...] [--workers 4]
// build_dir содержит timeline.json, sim.json, audio.wav. Кадр = draw(t) на странице, t = i / fps; видео H.264 + AAC.
const {chromium} = require("playwright");
const fs = require("fs"), path = require("path"), {spawn} = require("child_process");

async function main() {
  const [page_html, bdir, outp] = process.argv.slice(2);
  const arg = k => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : null; };
  const tl = JSON.parse(fs.readFileSync(path.join(bdir, "timeline.json")));
  const sim = JSON.parse(fs.readFileSync(path.join(bdir, "sim.json")));
  const browser = await chromium.launch();
  const open = async () => { const p = await browser.newPage({viewport: {width: 1080, height: 1920}});
    await p.goto("file://" + path.resolve(page_html)); await p.evaluate(d => window.init(d), {tl, sim});
    await p.evaluate(() => document.fonts.ready); return p; };
  const grab = async (p, t) => { const b64 = await p.evaluate(t => { window.draw(t); return document.getElementById("c").toDataURL("image/jpeg", 0.93).split(",")[1]; }, t);
    return Buffer.from(b64, "base64"); };
  if (arg("--stills")) {
    const p = await open(); fs.mkdirSync(outp, {recursive: true});
    for (const t of arg("--stills").split(",").map(Number)) fs.writeFileSync(path.join(outp, `t${t.toFixed(2)}.jpg`), await grab(p, t));
    await browser.close(); return;
  }
  const fps = tl.fps, N = Math.ceil(tl.duration * fps), workers = Number(arg("--workers") || 4);
  const ff = spawn("ffmpeg", ["-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(fps), "-c:v", "mjpeg", "-i", "-",
    "-i", path.join(bdir, "audio.wav"), "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", outp], {stdio: ["pipe", "inherit", "inherit"]});
  const pages = await Promise.all(Array.from({length: workers}, open));
  const t0 = Date.now();
  for (let i = 0; i < N; i += workers) { // параллельно по страницам, запись строго по порядку
    const bufs = await Promise.all(pages.map((p, k) => i + k < N ? grab(p, (i + k) / fps) : null));
    for (const b of bufs) if (b && !ff.stdin.write(b)) await new Promise(r => ff.stdin.once("drain", r));
    if (i % (fps * 10) < workers) process.stderr.write(`кадр ${i}/${N}, ${((Date.now() - t0) / 1000).toFixed(0)} с\n`);
  }
  ff.stdin.end(); await new Promise(r => ff.on("close", r)); await browser.close();
  console.log(`готово: ${N} кадров за ${((Date.now() - t0) / 1000).toFixed(0)} с → ${outp}`);
}
main().catch(e => { console.error(e); process.exit(1); });
