#!/usr/bin/env python3
"""Trích bảng ID âm thanh ("Wave/...") từ CA.exe.
Bảng là mảng con trỏ chuỗi tại địa chỉ ảo 0x917F70 (trong CA.exe.c: off_917F70[145]).
    python3 -I extract_sound_table.py CA.exe sound_table.json [0x917F70] [145]
Nếu exe của bạn là phiên bản khác, địa chỉ có thể khác: tìm "Wave/BomberWalk" trong exe,
hoặc tìm trong CA.exe.c dòng có chú thích // "Wave/BomberWalk" để lấy off_XXXXXX.
"""
import json, struct, sys

def main():
    exe, out = sys.argv[1], sys.argv[2]
    tab = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0x917F70
    cnt = int(sys.argv[4]) if len(sys.argv) > 4 else 145
    d = open(exe, 'rb').read()
    pe = struct.unpack_from('<I', d, 0x3c)[0]
    nsec = struct.unpack_from('<H', d, pe + 6)[0]; opt = struct.unpack_from('<H', d, pe + 20)[0]
    base = struct.unpack_from('<I', d, pe + 24 + 28)[0]
    secs, o = [], pe + 24 + opt
    for _ in range(nsec):
        vs, va, rs, rp = struct.unpack_from('<IIII', d, o + 8); secs.append((va, vs, rp, rs)); o += 40
    def v2o(v):
        r = v - base
        for va, vs, rp, rs in secs:
            if va <= r < va + max(vs, rs): return rp + (r - va)
        raise ValueError(hex(v))
    names = []
    for i in range(cnt):
        p = struct.unpack_from('<I', d, v2o(tab + 4 * i))[0]
        s = d[v2o(p):].split(b'\0', 1)[0].decode('latin1')
        if not s.startswith('Wave/'): break          # hết phần âm thanh
        names.append(s)
    json.dump({str(i): n for i, n in enumerate(names)}, open(out, 'w'), indent=1)
    print(len(names), 'âm thanh ->', out)

if __name__ == '__main__':
    main()
