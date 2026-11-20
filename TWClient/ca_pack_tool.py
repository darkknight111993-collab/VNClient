#!/usr/bin/env python3
"""Đọc index pack Crazy Arcade (.idx/.idd) – lấy MaskId từng file và giải mã file mã hóa.

Định dạng .idx (từ sub_6749C0/sub_673110 trong CA.exe, đã kiểm chứng trên Fx.idx):
  - Mã hóa dword: out[0]=K^in[0]; out[i]=out[i-1]^in[i]  (K=0x719CAB30 với các pack đã thử; nếu khác thì
    tự suy ra từ điều kiện dword đầu sau giải mã = 0). Byte lẻ cuối XOR theo dword cuối.
  - Sau giải mã: dword 0 (=0), 15 (marker bản mới), count; rồi count x
        { len, tên[len], offset, size, mask, checksum }
  - offset/size là vị trí trong file .idd. mask=0: dữ liệu không mã hóa; mask!=0: giải bằng
    ca_map_decrypt.decrypt(data, mask) (đã kiểm chứng: 50/50 file Map/* ra version 1000).

Dùng:
  python3 -I ca_pack_tool.py list Fx.idx [prefix]
  python3 -I ca_pack_tool.py manifest Fx.idx -o fx_masks.json         # path, offset, size, mask, checksum
  python3 -I ca_pack_tool.py extract Fx Map/Factory15 -o out.bin      # Fx = tên không đuôi (cần Fx.idx + Fx.idd)
  python3 -I ca_pack_tool.py extract-dir Fx Map -o out_dir            # giải mã cả nhánh, ghi <path>.dec
Cần ca_map_decrypt.py cạnh file này.
"""
import argparse, json, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ca_map_decrypt import decrypt

K_DEFAULT = 0x719CAB30


def dec_idx(b, K=K_DEFAULT):
    n = len(b) // 4
    w = struct.unpack('<%dI' % n, b[:n * 4])
    out = [0] * n
    out[0] = K ^ w[0]
    if out[0] != 0:                       # K khác: suy ra từ điều kiện dword đầu = 0
        K = w[0]; out[0] = 0
    for i in range(1, n):
        out[i] = out[i - 1] ^ w[i]
    res = bytearray(struct.pack('<%dI' % n, *out))
    last = out[-1]
    for j in range(len(b) - n * 4):
        res.append(b[n * 4 + j] ^ ((last >> (8 * j)) & 255))
    return bytes(res)


def parse_idx(raw):
    d = dec_idx(raw)
    c0, c1 = struct.unpack_from('<II', d, 0)
    if c0 != 0 or c1 != 15:
        raise ValueError('header idx không như mong đợi: %x %x (bản cũ?)' % (c0, c1))
    cnt = struct.unpack_from('<I', d, 8)[0]
    off, ents = 12, []
    for _ in range(cnt):
        ln = struct.unpack_from('<I', d, off)[0]; off += 4
        name = d[off:off + ln].decode('cp949', 'replace'); off += ln
        o, s, m, c = struct.unpack_from('<4I', d, off); off += 16
        ents.append({'path': name, 'offset': o, 'size': s, 'mask': m, 'checksum': c})
    return ents


def read_entry(idd, e):
    data = idd[e['offset']:e['offset'] + e['size']]
    return decrypt(data, e['mask']) if e['mask'] else data


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('list'); p.add_argument('idx'); p.add_argument('prefix', nargs='?', default='')
    p = sub.add_parser('manifest'); p.add_argument('idx'); p.add_argument('-o', default='masks.json')
    p = sub.add_parser('extract'); p.add_argument('pack'); p.add_argument('path'); p.add_argument('-o', required=True)
    p = sub.add_parser('extract-dir'); p.add_argument('pack'); p.add_argument('prefix'); p.add_argument('-o', required=True)
    a = ap.parse_args()
    if a.cmd in ('list', 'manifest'):
        ents = parse_idx(open(a.idx, 'rb').read())
        if a.cmd == 'list':
            for e in ents:
                if e['path'].startswith(a.prefix):
                    print('%10d %9d  mask=%08X  %s' % (e['offset'], e['size'], e['mask'], e['path']))
        else:
            json.dump(ents, open(a.o, 'w'), indent=1); print(len(ents), 'entries ->', a.o)
        return
    ents = parse_idx(open(a.pack + '.idx', 'rb').read())
    idd = open(a.pack + '.idd', 'rb').read()
    if a.cmd == 'extract':
        e = next(x for x in ents if x['path'] == a.path)
        open(a.o, 'wb').write(read_entry(idd, e)); print('ok', e['path'], len(read_entry(idd, e)), 'byte')
    else:
        n = 0
        for e in ents:
            if e['path'].startswith(a.prefix):
                dst = os.path.join(a.o, e['path'] + '.dec'); os.makedirs(os.path.dirname(dst), exist_ok=True)
                open(dst, 'wb').write(read_entry(idd, e)); n += 1
        print(n, 'file ->', a.o)


if __name__ == '__main__':
    main()
