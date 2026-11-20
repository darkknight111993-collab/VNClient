#!/usr/bin/env python3
"""Giải mã bảng ObjectTable (vd fxasset/ObjectTable/FxAssetObjectTable) của Crazy Arcade.

Cùng thuật toán với ca_map_decrypt.py (đặt hai file cạnh nhau). Mask không biết trước,
nên tự dò: dword đầu = số entry (nhỏ), dword thứ hai = độ dài tên (<128) =>
24 bit cao của mask suy ra được, 8 bit thấp thử 256 giá trị và kiểm tra bằng cách parse:
    count, rồi count x [len(<128), tên ASCII, int offset]

    python3 -I ca_table_decrypt.py raw.bin [--mask 0x...] [--dec out.bin]
"""
import argparse, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ca_map_decrypt import decrypt


def parse_index(dec):
    n = struct.unpack_from('<i', dec, 0)[0]
    if not 0 < n < 100000:
        return None
    off, out = 4, []
    for _ in range(n):
        if off + 4 > len(dec): return None
        ln = struct.unpack_from('<I', dec, off)[0]; off += 4
        if ln >= 0x80 or off + ln + 4 > len(dec): return None
        s = dec[off:off + ln]
        if any(c < 32 or c > 126 for c in s): return None
        off += ln
        out.append((s.decode(), struct.unpack_from('<i', dec, off)[0])); off += 4
    return out, off


def find_mask(data):
    base = decrypt(data, 0)
    hi = (struct.unpack_from('<I', base, 4)[0] >> 8) << 8
    for low in range(256):
        if parse_index(decrypt(data, hi | low)):
            return hi | low
    return None


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('--mask', type=lambda s: int(s, 0)); ap.add_argument('--dec')
    a = ap.parse_args()
    data = open(a.file, 'rb').read()
    mask = a.mask if a.mask is not None else find_mask(data)
    if mask is None: sys.exit('không dò được mask - truyền --mask')
    dec = decrypt(data, mask)
    if a.dec: open(a.dec, 'wb').write(dec)
    idx, end = parse_index(dec)
    print('mask 0x%08X, %d entry, index kết thúc ở byte %d / %d' % (mask, len(idx), end, len(dec)))
    for name, off in idx: print('%8d  %s' % (off, name))
