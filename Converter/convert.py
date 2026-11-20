#!/usr/bin/env python3
"""
BnB / Crazy Arcade asset converter  ->  Godot 4 friendly files.

    python Converter/convert.py                   # convert everything (parallel, resumable)
    python Converter/convert.py --only fx/MP3     # only paths starting with this prefix
    python Converter/convert.py --force           # redo even if already converted
    python Converter/convert.py --workers 4 --limit 100

Every source file  ExtractedAssets/<archive>/<dir>/<Name>
becomes a folder   AssetsDecoded/<archive>/<dir>/<Name>/  holding the decoded files.
No third party packages are needed (pure Python 3.8+).
"""
import argparse, json, os, shutil, struct, sys, time, traceback, zlib
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sprite as spr

VERSION = 2
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'ExtractedAssets')
DST = os.path.join(ROOT, 'AssetsDecoded')


# ------------------------------------------------------------------ detection
def try_text(b):
    """Return (encoding, text) when b is a (length-prefixed) text file, else None."""
    body = b
    if len(b) >= 4 and struct.unpack('<I', b[:4])[0] == len(b) - 4:
        body = b[4:]
    if body[:2] == b'\xff\xfe':
        try: return 'utf-16', body.decode('utf-16')
        except Exception: return None
    if body[:3] == b'\xef\xbb\xbf':
        return 'utf-8', body[3:].decode('utf-8', 'replace')
    if not body: return None
    bad = sum(1 for c in body[:4096] if c < 9 or (13 < c < 32))
    if bad > 0: return None
    for enc in ('utf-8', 'cp949'):
        try: return enc, body.decode(enc)
        except Exception: pass
    return None


def detect(b):
    if b[:4] == b'OggS': return 'ogg'
    if b[:3] == b'\xff\xd8\xff': return 'jpeg'
    if b[:8] == b'PACK0001': return 'pack'
    if b[:4] == b'RIFF' and b[8:12] == b'WAVE': return 'wav'
    if b[:8] == b'\x89PNG\r\n\x1a\n': return 'png'
    u = spr.unwrap(b)
    if len(u) > 16:
        try:
            d, f, im, rest = spr.parse(u)
            if rest == 0: return 'sprite'
        except Exception: pass
    if try_text(b): return 'text'
    if u is not b:
        t = detect(u)
        if t != 'unknown': return 'zlib+' + t
    return 'unknown'


# ------------------------------------------------------------------ converters
def pick_bpp(hdr_x, data, w, h):
    order = (2, 3, 4, 1) if hdr_x > 1000 else (3, 2, 4, 1)
    for bpp in order:
        try:
            if spr.tokens(data, w, h, bpp)[1]: return bpp
        except Exception: pass
    return None


def conv_sprite(b, out, rel, meta):
    b = spr.unwrap(b)
    dims, frames, imgs, rest = spr.parse(b)
    hdr_x = struct.unpack('<i', b[12:16])[0]
    os.makedirs(os.path.join(out, 'images'), exist_ok=True)
    info = {'format': 'bnb-sprite-v2', 'header_x': hdr_x, 'images': [], 'frames': []}
    rgba_cache = {}
    for k, ((h, w), data) in enumerate(zip(dims, imgs)):
        rec = {'index': k, 'width': w, 'height': h, 'file': None}
        if w > 0 and h > 0 and data:
            bpp = pick_bpp(hdr_x, data, w, h)
            if bpp is None:
                rec['error'] = 'undecodable pixel stream'
                meta.setdefault('warnings', []).append('image %d undecodable' % k)
            else:
                rgba = spr.render(data, w, h, bpp, '565')
                rgba_cache[k] = (w, h, rgba)
                rec.update(file='images/image_%04d.png' % k, bpp=bpp * 8)
                with open(os.path.join(out, rec['file']), 'wb') as f:
                    f.write(spr.png_bytes(w, h, rgba))
        info['images'].append(rec)
    os.makedirs(os.path.join(out, 'frames'), exist_ok=True)
    for n, fr in enumerate(frames):
        ox, oy, flag, img, x0, y0, x1, y1, a, b2, c, d = fr
        rec = {'index': n, 'image': img, 'offset': [ox, oy], 'flag': flag,
               'rect': [x0, y0, x1, y1], 'extra': [a, b2, c, d], 'file': None}
        if img in rgba_cache:
            w, h, rgba = rgba_cache[img]
            cx0, cy0, cx1, cy1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
            if cx1 > cx0 and cy1 > cy0:
                rows = [rgba[(y * w + cx0) * 4:(y * w + cx1) * 4] for y in range(cy0, cy1)]
                rec['file'] = 'frames/frame_%04d.png' % n
                rec['size'] = [cx1 - cx0, cy1 - cy0]
                with open(os.path.join(out, rec['file']), 'wb') as f:
                    f.write(spr.png_bytes(cx1 - cx0, cy1 - cy0, b''.join(rows)))
        info['frames'].append(rec)
    if not any(r['file'] for r in info['frames']): shutil.rmtree(os.path.join(out, 'frames'), ignore_errors=True)
    with open(os.path.join(out, 'sprite.json'), 'w', encoding='utf-8') as f:
        json.dump(info, f, indent=1)
    write_tres(out, rel, info)
    meta['frames'] = len(frames); meta['images'] = len(imgs)


def write_tres(out, rel, info):
    """Godot 4 SpriteFrames resource (one 'default' animation made of all frames)."""
    fr = [r for r in info['frames'] if r['file']]
    if not fr: return
    prefix = 'res://AssetsDecoded/' + rel.replace('\\', '/')
    lines = ['[gd_resource type="SpriteFrames" load_steps=%d format=3]' % (len(fr) + 1), '']
    for i, r in enumerate(fr):
        lines.append('[ext_resource type="Texture2D" path="%s/%s" id="%d"]' % (prefix, r['file'], i + 1))
    lines += ['', '[resource]', 'animations = [{', '"frames": [']
    lines.append(',\n'.join('{\n"duration": 1.0,\n"texture": ExtResource("%d")\n}' % (i + 1) for i in range(len(fr))))
    lines += ['],', '"loop": true,', '"name": &"default",', '"speed": 10.0', '}]']
    with open(os.path.join(out, 'frames.tres'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')


def conv_text(b, out, rel, meta):
    enc, text = try_text(b)
    ext = 'xml' if text.lstrip('\ufeff \r\n\t').startswith('<') else 'txt'
    with open(os.path.join(out, 'data.' + ext), 'w', encoding='utf-8', newline='') as f:
        f.write(text)
    meta['encoding'] = enc


def conv_pack(b, out, rel, meta):
    cnt, idxsz = struct.unpack('<2I', b[8:16])
    do = zlib.decompressobj()
    idx = do.decompress(b[16:])
    with open(os.path.join(out, 'index.bin'), 'wb') as f: f.write(idx)
    rest = do.unused_data
    meta['pack_entries'] = cnt
    sub = []
    try:
        clen, rlen = struct.unpack('<2I', rest[:8])
        payload = zlib.decompress(rest[8:8 + clen])
        # payload = several sprite files stored back to back
        pos, n = 0, 0
        while pos < len(payload):
            try:
                _, _, _, end = spr.parse(payload, pos, True)
                if end > len(payload): raise ValueError('truncated')
            except Exception:
                open(os.path.join(out, 'tail.bin'), 'wb').write(payload[pos:])
                meta.setdefault('warnings', []).append('%d trailing bytes at %d are not a sprite (kept as tail.bin)' % (len(payload) - pos, pos))
                break
            sub_dir = os.path.join(out, 'entry_%02d' % n); os.makedirs(sub_dir, exist_ok=True)
            m2 = {}
            conv_sprite(payload[pos:end], sub_dir, rel + '/entry_%02d' % n, m2)
            pos, n = end, n + 1
        meta['payload_type'] = 'sprites'; meta['payload_entries'] = n
    except Exception as e:
        with open(os.path.join(out, 'payload.bin'), 'wb') as f: f.write(rest)
        meta.setdefault('warnings', []).append('payload not decoded: %s' % e)


def run_converter(kind, b, out, rel, meta):
    if kind == 'ogg':
        open(os.path.join(out, 'sound.ogg'), 'wb').write(b)
    elif kind == 'wav':
        open(os.path.join(out, 'sound.wav'), 'wb').write(b)
    elif kind == 'jpeg':
        open(os.path.join(out, 'image.jpg'), 'wb').write(b)
    elif kind == 'png':
        open(os.path.join(out, 'image.png'), 'wb').write(b)
    elif kind == 'sprite':
        conv_sprite(b, out, rel, meta)
    elif kind == 'text':
        conv_text(b, out, rel, meta)
    elif kind == 'pack':
        conv_pack(b, out, rel, meta)
    elif kind.startswith('zlib+'):
        run_converter(kind[5:], spr.unwrap(b), out, rel, meta)
    else:
        open(os.path.join(out, 'raw.bin'), 'wb').write(b)
        meta['status'] = 'unsupported'
        meta['note'] = 'unknown/encrypted format - raw copy kept'


def convert_one(args):
    src, rel, force = args
    out = os.path.join(DST, rel)
    mpath = os.path.join(out, 'meta.json')
    if not force and os.path.exists(mpath):
        try:
            m = json.load(open(mpath, encoding='utf-8'))
            if m.get('converter_version') == VERSION: return rel, m.get('type'), m.get('status'), 'skipped'
        except Exception: pass
    meta = {'source': rel.replace('\\', '/'), 'converter_version': VERSION, 'status': 'ok'}
    try:
        if os.path.isdir(out): shutil.rmtree(out)
        os.makedirs(out, exist_ok=True)
        b = open(src, 'rb').read()
        meta['size'] = len(b)
        kind = detect(b); meta['type'] = kind
        run_converter(kind, b, out, rel, meta)
    except Exception as e:
        meta['status'] = 'error'; meta['error'] = '%s: %s' % (type(e).__name__, e)
        meta['trace'] = traceback.format_exc()[-800:]
    os.makedirs(out, exist_ok=True)
    with open(mpath, 'w', encoding='utf-8') as f: json.dump(meta, f, indent=1)
    return rel, meta.get('type'), meta['status'], meta.get('error')


# ------------------------------------------------------------------ main
def scan(only):
    items = []
    for archive in sorted(os.listdir(SRC)):
        ad = os.path.join(SRC, archive)
        if not os.path.isdir(ad): continue
        for r, _, fs in os.walk(ad):
            for f in fs:
                if r == ad and f == 'manifest.json': continue
                p = os.path.join(r, f)
                rel = os.path.relpath(p, SRC)
                if only and not rel.replace('\\', '/').startswith(only): continue
                items.append((p, rel))
    return items


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--only', default='', help='convert only relative paths starting with this (e.g. fx/MP3)')
    ap.add_argument('--force', action='store_true', help='re-convert already converted files')
    ap.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 2)))
    ap.add_argument('--limit', type=int, default=0, help='debug: only first N files')
    a = ap.parse_args()
    t0 = time.time()
    items = scan(a.only.replace('\\', '/'))
    if a.limit: items = items[:a.limit]
    os.makedirs(DST, exist_ok=True)
    for archive in os.listdir(SRC):
        m = os.path.join(SRC, archive, 'manifest.json')
        if os.path.exists(m):
            os.makedirs(os.path.join(DST, archive), exist_ok=True)
            shutil.copyfile(m, os.path.join(DST, archive, 'manifest.json'))
    print('Converting %d files with %d workers ...' % (len(items), a.workers))
    stats, results, errors = {}, [], []
    jobs = [(p, rel, a.force) for p, rel in items]
    with ProcessPoolExecutor(a.workers) as ex:
        for n, res in enumerate(ex.map(convert_one, jobs, chunksize=16), 1):
            rel, kind, status, err = res
            results.append(res)
            k = (kind, status); stats[k] = stats.get(k, 0) + 1
            if status != 'ok': errors.append(res)
            if n % 500 == 0 or n == len(jobs):
                print('  %d/%d  (%.0fs)' % (n, len(jobs), time.time() - t0), flush=True)
    report = {'files': len(items), 'seconds': round(time.time() - t0, 1),
              'by_type': {'%s/%s' % (k[0], k[1]): v for k, v in sorted(stats.items(), key=lambda x: str(x))},
              'problems': [{'file': r[0].replace('\\', '/'), 'type': r[1], 'status': r[2], 'error': r[3]} for r in errors]}
    with open(os.path.join(DST, '_report.json'), 'w', encoding='utf-8') as f: json.dump(report, f, indent=1)
    print('\nDone in %.0fs. Summary (type/status: count):' % (time.time() - t0))
    for k, v in report['by_type'].items(): print('  %-28s %d' % (k, v))
    print('Problems: %d  (see AssetsDecoded/_report.json)' % len(errors))


if __name__ == '__main__':
    main()
