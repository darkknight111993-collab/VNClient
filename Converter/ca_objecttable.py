#!/usr/bin/env python3
"""Giải mã ObjectTable/ObjectTable của Crazy Arcade và xuất JSON: id -> tên, sprite, trạng thái.

Cần ca_map_decrypt.py + ca_table_decrypt.py cạnh file này.
    python3 -I ca_objecttable.py raw.bin -o objecttable.json [--mask 0x...]

id của ô trong map (object/ground) chính là chỉ số trong danh sách này (đã kiểm tra: 1121 = Tile03_Box/BoxBlue,
1147 = Tile03_Static/Block00, 1139 = Tile03_Ground/Tile03 ...).
Bản ghi sau index: [số state] x { len,tên state, len,đường dẫn sprite, n, n x (frame, duration) }.
"""
import argparse, json, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ca_map_decrypt import decrypt
from ca_table_decrypt import find_mask, parse_index


def parse_record(r):
    off = 0
    def i32():
        nonlocal off
        v = struct.unpack_from('<i', r, off)[0]; off += 4; return v
    def s():
        nonlocal off
        n = i32(); v = r[off:off + n].decode('cp949', 'replace'); off += n; return v
    states = []
    for _ in range(i32()):
        name, sprite = s(), s()
        n = i32()
        frames = [(i32(), i32()) for _ in range(n)]
        states.append({'state': name, 'sprite': sprite, 'frames': frames})
    if off != len(r):
        raise ValueError('lệch %d byte' % (len(r) - off))
    return states


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('-o', '--json', default='objecttable.json')
    ap.add_argument('--mask', type=lambda x: int(x, 0))
    a = ap.parse_args()
    data = open(a.file, 'rb').read()
    mask = a.mask if a.mask is not None else find_mask(data)
    if mask is None: sys.exit('không dò được mask')
    dec = decrypt(data, mask)
    idx, end = parse_index(dec)
    offs = sorted({o for _, o in idx if o >= 0}) + [len(dec)]
    nxt = {o: offs[k + 1] for k, o in enumerate(offs[:-1])}
    out, bad = [], 0
    for i, (name, o) in enumerate(idx):
        e = {'id': i, 'name': name, 'states': None}
        if o >= 0:
            try: e['states'] = parse_record(dec[o:nxt[o]])
            except Exception as ex: e['error'] = str(ex); bad += 1
        out.append(e)
    json.dump(out, open(a.json, 'w'), ensure_ascii=False, indent=1)
    print('mask 0x%08X, %d mục, %d bản ghi lỗi -> %s' % (mask, len(out), bad, a.json))


if __name__ == '__main__':
    main()
