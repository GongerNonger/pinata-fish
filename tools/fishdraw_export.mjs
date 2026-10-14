// Export fishdraw fish (Lingdong Huang, MIT) as plain shape data for tools/build_pinata_fish.py.
//   node tools/fishdraw_export.mjs [seed seed ...]      -> art/pinata/fishdraw/fish_<seed>.json
// fishdraw is read from ./fishdraw (clone it there, or set FISHDRAW to its fishdraw.js) and hooked in memory;
// nothing in that folder is modified. Each file holds the side silhouette as a top and bottom edge sampled
// along the body, every fin outline, and the eye, in units of body length with the nose at t = 0 and +z up.
import fs from 'node:fs';
import vm from 'node:vm';

const SRC = process.env.FISHDRAW || new URL('../fishdraw/fishdraw.js', import.meta.url);
const OUT = new URL('../art/pinata/fishdraw/', import.meta.url);
const SEEDS = process.argv.slice(2).map(Number);
const COLS = 64;

function loadFishdraw() {
  let code = fs.readFileSync(SRC, 'utf8');
  const before = code;
  code = code.replace(/return bd\.\s*\n\s*concat\(f0\)/, m =>
    'globalThis.__parts = {outline,c0,c1,c2,c3,c4,c5};\n  ' + m);
  if (code === before) throw new Error('fishdraw hook point not found');
  code = code.replace(/function fish_eye_([ab])\(ex,ey,rad\)\{/g, m => m + ' globalThis.__eye=[ex,ey,rad];');
  const b2 = code;
  code = code.replace(/let outlinel = \[\[0,0\]/, m => 'globalThis.__head = {outline, jc, lip0, lip1};\n  ' + m);
  if (code === b2) throw new Error('fish_head hook point not found');
  code += '\n;globalThis.__api={generate_params,fish,str_to_seed,binomen,setSeed:(s)=>{jsr=s;}};';
  const ctx = vm.createContext({ console, Math });
  vm.runInContext(code, ctx);
  return ctx;
}

// Lowest and highest y where a vertical line at x crosses any of the polygons.
function span(polys, x) {
  let lo = Infinity, hi = -Infinity;
  for (const pl of polys) {
    for (let i = 0; i < pl.length; i++) {
      const [x0, y0] = pl[i], [x1, y1] = pl[(i + 1) % pl.length];
      if ((x0 - x) * (x1 - x) > 0 || x0 === x1) continue;
      const y = y0 + (y1 - y0) * (x - x0) / (x1 - x0);
      if (y < lo) lo = y;
      if (y > hi) hi = y;
    }
  }
  return [lo, hi];
}

const ctx = loadFishdraw();
fs.mkdirSync(OUT, { recursive: true });
for (const seed of SEEDS) {
  const api = ctx.__api;
  api.setSeed(seed);
  const name = api.binomen();
  api.setSeed(api.str_to_seed(name));
  api.fish(api.generate_params());
  const P = ctx.__parts, HD = ctx.__head, eye = ctx.__eye;
  const body = [P.outline, HD.outline, HD.jc].filter(q => q && q.length > 2);
  let x0 = Infinity, x1 = -Infinity;
  for (const pl of body) for (const [x] of pl) { if (x < x0) x0 = x; if (x > x1) x1 = x; }
  const len = x1 - x0;
  const raw = [];
  for (let i = 0; i <= COLS; i++) raw.push(span(body, x0 + len * (0.004 + 0.992 * i / COLS)));
  const mids = raw.filter(([lo, hi]) => isFinite(lo)).map(([lo, hi]) => (lo + hi) / 2);
  const base = mids.reduce((a, b) => a + b, 0) / mids.length;
  const Z = y => +(-(y - base) / len).toFixed(4);          // fishdraw y runs down
  const T = x => +((x - x0) / len).toFixed(4);
  const cols = raw.map(([lo, hi]) => isFinite(lo) ? { top: Z(lo), bot: Z(hi) } : null);
  const fin = pl => pl && pl.length > 2 ? pl.filter((_, i) => i % Math.max(1, Math.floor(pl.length / 40)) === 0).map(([x, y]) => [T(x), Z(y)]) : null;
  const data = {
    name, seed, cols,
    fins: { median: [P.c0, P.c3, P.c4, P.c5].map(fin).filter(Boolean), pectoral: fin(P.c1), pelvic: fin(P.c2) },
    eye: eye ? [T(eye[0]), Z(eye[1]), +(eye[2] / len).toFixed(4)] : null,
  };
  fs.writeFileSync(new URL(`fish_${seed}.json`, OUT), JSON.stringify(data));
  console.log(seed, name, 'fins', data.fins.median.length, 'eye', data.eye);
}
