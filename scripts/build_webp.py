#!/usr/bin/env python3
"""Build WebP copies of the tree art next to the PNG masters (PNGs stay as the Safari<14 fallback).

    python3 scripts/build_webp.py                 # default dirs, scale 0.5, q90
    python3 scripts/build_webp.py static/img/new_kit --scale 0.5
    python3 scripts/build_webp.py --check         # exit 1 if any .webp is missing/stale

Works on ANY kit: every *.png under the given dirs (pass dirs explicitly; oak pixel kit removed)
becomes <name>.webp beside it, plus every kit.json is minified in place (same data, no whitespace).

Why scale 0.5: pieces are laid out from kit.json `size` (world px) and drawn with explicit CSS
width/height, so the file's pixel size never changes layout. Measured (perf_r1, WebKit 390@2x and
1440@2x): the largest on-screen size of any kit piece is <=0.35 of its native PNG (trunk_core
2048px -> 644 CSS px at 1440), i.e. 0.5 keeps >=2x phone and >=1.4x desktop-retina headroom.
Pieces smaller than --min-px on their long side are left at native size. Alpha is kept
(alpha_quality 100, exact=True keeps RGB under transparent pixels for clean edges).
Skips files whose .webp is newer than the .png (use --force to rebuild).
"""
import argparse, json, os, sys
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# dir -> scale. Soil/grass bands are stretched full-width as CSS backgrounds, so they keep native size.
DEFAULT_DIRS = {}  # oak pixel kit removed


def convert(src, dst, scale, quality, min_px):
    im = Image.open(src)
    im.load()
    if im.mode not in ('RGBA', 'RGB'):
        im = im.convert('RGBA')
    w, h = im.size
    if scale < 1 and max(w, h) * scale >= min_px:
        im = im.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
    im.save(dst, 'WEBP', quality=quality, alpha_quality=100, method=6, exact=True)


def minify_json(path):
    raw = open(path, 'rb').read()
    data = json.loads(raw)
    out = json.dumps(data, separators=(',', ':'), ensure_ascii=False).encode()
    assert json.loads(out) == data
    if out != raw:
        open(path, 'wb').write(out)
    return len(raw), len(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='*')
    ap.add_argument('--scale', type=float, default=None, help='override scale for all dirs')
    ap.add_argument('--quality', type=int, default=90)
    ap.add_argument('--min-px', type=int, default=64)
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    stale, n, before, after = [], 0, 0, 0
    dirs = {d: (a.scale or 0.5) for d in a.dirs} if a.dirs else {d: (a.scale or s) for d, s in DEFAULT_DIRS.items()}
    for d, scale in dirs.items():
        d = os.path.join(ROOT, d) if not os.path.isabs(d) else d
        for dp, _, files in os.walk(d):
            for f in sorted(files):
                p = os.path.join(dp, f)
                if f == 'kit.json' and not a.check:
                    b, o = minify_json(p)
                    print(f'minified {os.path.relpath(p, ROOT)}: {b} -> {o} bytes')
                if not f.endswith('.png'):
                    continue
                w = p[:-4] + '.webp'
                fresh = os.path.exists(w) and os.path.getmtime(w) >= os.path.getmtime(p)
                if a.check:
                    if not fresh:
                        stale.append(p)
                    continue
                if fresh and not a.force:
                    continue
                convert(p, w, scale, a.quality, a.min_px)
                n += 1
                before += os.path.getsize(p)
                after += os.path.getsize(w)
    if a.check:
        for s in stale:
            print('stale/missing webp:', os.path.relpath(s, ROOT))
        sys.exit(1 if stale else 0)
    print(f'converted {n} png -> webp: {before/1e6:.1f} MB -> {after/1e6:.1f} MB')


if __name__ == '__main__':
    main()
