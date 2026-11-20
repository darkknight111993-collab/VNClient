#!/usr/bin/env python3
"""Giải mã + đọc file map Crazy Arcade / BnB (ví dụ fx/Map/Factory15).

Thuật toán lấy từ CA.exe (hàm sub_6731A0 = giải mã, sub_4E5845 = đọc map):
    out[0] = mask ^ in[0] ^ 0x9C6C95CE
    out[i] = in[i] ^ (i*i*(i+966)*(i+2020)) ^ out[i-1] ^ 0x9C6C95CE      (dword, little endian, mod 2^32)
    byte lẻ cuối (n%4): out_byte[j] = in_byte[j] ^ ((out[last] >> 8*j) & 0xFF)

`mask` (MaskId) là khóa riêng của từng file, game lấy từ bảng/header của pack.
Ở đây mask được suy ra bằng known-plaintext (version 1000/1001/1002 hoặc trường header = 0)
và kiểm tra khớp tới byte cuối cùng (1019/1019 map). Có thể ép bằng --mask nếu cần.

Cách dùng:
    python3 -I ca_map_decrypt.py raw.bin                 # in thông tin + bản đồ ASCII
    python3 -I ca_map_decrypt.py raw.bin -o map.json     # xuất JSON
    python3 -I ca_map_decrypt.py raw.bin --dec out.bin   # xuất bản giải mã thô
    python3 -I ca_map_decrypt.py --batch AssetsDecoded/fx/Map   # hàng loạt: mỗi <thư mục>/raw.bin -> <thư mục>/map.json + script.xml
"""
import argparse, json, os, re, struct, sys

M32 = 0xFFFFFFFF
KEY = 0x9C6C95CE
VERSION = 1000

THEME_BGM = {
    'antarctic': 'M_Antarctic_NM',
    'aqua': 'Aqua',
    'blackrabbit': 'Rabbit',
    'bonus': 'Bonus',
    'bonusbig': 'Bonus',
    'bonusbigrpg': 'Bonus',
    'bonusbigreward': 'Bonus',
    'bonuscp': 'Bonus',
    'bonusdark': 'Bonus',
    'bonusexp': 'Bonus',
    'bonuslargegourd': 'Bonus',
    'bonusmazemap': 'Bonus',
    'bonussnowball': 'SnowBallFight',
    'bula': 'Bula',
    'cahero': 'CAHero_Legend',
    'camp': 'Camp',
    'cemetery': 'Cemetery',
    'clover': 'Clover',
    'clovertest': 'Clover',
    'confusedfight': 'ConfusedFight_Normal',
    'cookie': 'Cookie',
    'darkknight': 'CAHero_DarkHero',
    'desert': 'Desert',
    'eventcamp': 'EventBgm',
    'eventfactory': 'EventBgm',
    'eventforest': 'EventBgm',
    'eventocean': 'EventBgm',
    'eventpatrit': 'EventBgm',
    'exbula': 'Bula',
    'excamp': 'Camp',
    'exfactory': 'Factory',
    'exforest': 'Forest',
    'expatrit': 'Patrit',
    'extomb': 'Tomb',
    'exvillage': 'Village',
    'factory': 'Factory',
    'fighteroflegend': 'FigtherOfLegend',
    'forest': 'Forest',
    'fortunestar': 'CAHero_FortuneStar',
    'goldflag': 'Camp',
    'goldenbonuswriggle': 'Bonus',
    'golemrun': 'M_GR_NormalStage',
    'hidden': 'hiddencatch_Normalmode',
    'hiddencatchtest': 'hiddencatch_Normalmode',
    'iamboss': 'IamBoss',
    'ice': 'Ice',
    'javelin': 'Camp',
    'kart': 'Kart',
    'kfg': 'Kfg',
    'ladder': 'Village',
    'lobbycaffe': 'LobbySquare',
    'lobbyclothing': 'LobbySquare',
    'lobbyjewelry': 'LobbySquare',
    'lobbypet': 'LobbySquare',
    'lobbysquare': 'LobbySquare',
    'lobbysquarefishingtest': 'LobbySquare',
    'mine': 'Mine',
    'monbig': 'M_G_NormalStage',
    'mongolem': 'M_G_NormalStage',
    'monhorde': 'M_G2_BossStage',
    'monpen': 'M_P_NormalStage',
    'monrobot': 'M_R_NormalStage',
    'mons': 'M_S_NormalStage',
    'monseal': 'M_S_NormalStage',
    'monsnowbear': 'M_Snow_NormalStage',
    'monturtle': 'M_T_NormalStage',
    'monunlimited': 'M_M2_NormalStage',
    'monster': 'M_P_NormalStage',
    'nxcl': 'Village',
    'ocean': 'Ocean',
    'olympickart': 'Kart',
    'olympicrun': 'Camp',
    'olympicshoot': 'Camp',
    'pangland': 'PangLand',
    'patrit': 'Patrit',
    'pharaoh': 'Tomb',
    'rpg': 'RPGIntro',
    'rabbit': 'Rabbit',
    'seafields': 'Ocean',
    'shopmap': 'Prepare',
    'snowballfight': 'SnowBallFight',
    'snowyfields': 'Ice',
    'square': 'StageSquare',
    'super': 'SuperFighter',
    'superfighter': 'SuperFighter',
    'superspecial': 'SuperFighter2',
    'sweetcandy': 'Cookie',
    'tlshopmap': 'Prepare',
    'tomb': 'Tomb',
    'tournament': 'Camp',
    'usercontest': 'Village',
    'village': 'Village',
    'whiteangel': 'CAHero_WhiteAngel',
    'winningstreak': 'SuperFighter',
    'wriggle': 'Wriggle',
    'wriggletest': 'Wriggle',
    'ws': 'SuperFighter',
    'xmas': 'Xmas',
    'zombie': 'Zombie',
    'zzolman': 'Zzolman',
}


def decrypt(data: bytes, mask: int) -> bytes:
    n = len(data) // 4
    c = struct.unpack('<%dI' % n, data[:n * 4])
    out = [0] * n
    if n:
        out[0] = (mask ^ c[0] ^ KEY) & M32
        for i in range(1, n):
            f = (i * i * (i + 966) * (i + 2020)) & M32
            out[i] = (c[i] ^ f ^ out[i - 1] ^ KEY) & M32
    res = bytearray(struct.pack('<%dI' % n, *out))
    last = out[-1] if n else mask
    for j in range(len(data) - n * 4):
        res.append(data[n * 4 + j] ^ ((last >> (8 * j)) & 0xFF))
    return bytes(res)


def guess_mask(data: bytes) -> int:
    c0 = struct.unpack('<I', data[:4])[0]
    for v in (1000, 1001, 1002, 1003, 15, 13, 14):
        m = (c0 ^ KEY ^ v) & M32
        try:
            parse(decrypt(data, m))
            return m
        except Exception:
            pass
    base = decrypt(data[:64], 0)
    u = struct.unpack_from('<16I', base, 0)
    for m in (u[7], u[8], u[9], u[10], u[1] ^ 8, u[1] ^ 1, u[1] ^ 2):
        try:
            parse(decrypt(data, m))
            return m
        except Exception:
            pass
    return (c0 ^ KEY ^ VERSION) & M32


def resolve_bgm(map_name: str, script_xml: str) -> dict:
    bgm_info = {}
    if script_xml:
        for attr in ('bgm', 'bgmExt01', 'bgmExt02'):
            m = re.search(r'\b' + attr + r'\s*=\s*"([^"]+)"', script_xml, re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                track = val.split(',')[0].split('/')[-1]
                bgm_info[attr] = 'fx/MP3/%s/sound.ogg' % track
                if ',' in val:
                    bgm_info[attr + '_delay_ms'] = int(val.split(',')[1])
    if 'bgm' not in bgm_info:
        prefix = re.sub(r'[0-9_]+.*$', '', map_name or '').lower()
        track = THEME_BGM.get(prefix, 'Village')
        bgm_info['bgm'] = 'fx/MP3/%s/sound.ogg' % track
        if prefix == 'xmas':
            bgm_info['bgm_variants'] = ['fx/MP3/Carol%02d/sound.ogg' % i for i in range(4)] + ['fx/MP3/Xmas/sound.ogg']
        elif prefix == 'kart':
            bgm_info['bgm_hurry'] = 'fx/MP3/KartFast/sound.ogg'
        elif prefix in ('rabbit', 'blackrabbit'):
            bgm_info['bgm_hurry'] = 'fx/MP3/Rabbit_HurryUp/sound.ogg'
        elif prefix == 'zombie':
            bgm_info['bgm_hurry'] = 'fx/MP3/Zombie10s/sound.ogg'
        elif prefix == 'iamboss':
            bgm_info['bgm_hurry'] = 'fx/MP3/IamBoss10s/sound.ogg'
    return bgm_info


def parse(dec: bytes, map_name: str = '') -> dict:
    n = len(dec) // 4
    if n < 20:
        raise ValueError('file quá ngắn (%d byte)' % len(dec))
    w = list(struct.unpack('<%di' % n, dec[:n * 4]))
    if w[0] < 1000:
        version, h1, h2, cols, rows = 0, 8, 1, w[0], w[1]
        hdr_end = 16
        nsp = w[2]
        cell_stride = 2
    else:
        version, h1, h2, cols, rows = w[0], w[1], w[2], w[3], w[4]
        hdr_end = 19
        nsp = w[5]
        cell_stride = 3 if version >= 1001 else 2
    if not (0 <= version <= 1010 and 0 < cols <= 256 and 0 < rows <= 256 and 0 <= nsp <= 200):
        raise ValueError('header không hợp lệ: version=%d cols=%d rows=%d nsp=%d' % (version, cols, rows, nsp))
    info = {
        'version': version, 'h1': h1, 'h2': h2,
        'cols': cols, 'rows': rows,
        'header_raw': w[:hdr_end],
    }
    info['spawns'] = [[w[hdr_end + 2 * k], w[hdr_end + 2 * k + 1]] for k in range(nsp)]
    p = hdr_end + 2 * nsp
    cnt = w[p]; p += 1
    if not (0 <= cnt <= 200):
        raise ValueError('cnt extra_list không hợp lệ: %d' % cnt)
    info['extra_list'] = [w[p + 4 * k:p + 4 * k + 4] for k in range(cnt)]
    p += 4 * cnt
    if p + cell_stride * cols * rows > n:
        raise ValueError('thiếu dữ liệu lưới (%dx%d)' % (cols, rows))
    grid = []
    for y in range(rows):
        row = []
        for x in range(cols):
            if cell_stride == 2:
                row.append({'ground': w[p], 'object': w[p + 1]})
            else:
                row.append({'ground': w[p], 'object': w[p + 1], 'extra': w[p + 2]})
            p += cell_stride
        grid.append(row)
    info['grid'] = grid
    info['after_grid_index'] = p
    off = p * 4
    count = struct.unpack_from('<i', dec, off)[0]; off += 4
    if not (0 <= count <= 1000):
        raise ValueError('số vật phẩm không hợp lệ: %d' % count)
    items = []
    for _ in range(count):
        if off + 4 > len(dec):
            raise ValueError('thiếu dữ liệu vật phẩm')
        ln = struct.unpack_from('<i', dec, off)[0]; off += 4
        if not (0 <= ln <= 256) or off + ln + 4 > len(dec):
            raise ValueError('độ dài tên vật phẩm không hợp lệ: %d' % ln)
        s = dec[off:off + ln]
        if any(c < 9 or (13 < c < 32) for c in s.split(b'\0')[0]):
            raise ValueError('tên vật phẩm chứa ký tự điều khiển')
        name = s.split(b'\0')[0].decode('cp949', 'replace'); off += ln
        weight = struct.unpack_from('<i', dec, off)[0]; off += 4
        items.append({'name': name, 'weight': weight})
    info['items'] = items
    info['item_drop_rate'] = struct.unpack_from('<i', dec, off)[0]; off += 4
    # 1. Vật phẩm cố định tại ô (cell_items: name, x, y, chance)
    n_cell_items = struct.unpack_from('<i', dec, off)[0]; off += 4
    if not (0 <= n_cell_items <= 5000):
        raise ValueError('n_cell_items không hợp lệ: %d' % n_cell_items)
    cell_items = []
    for _ in range(n_cell_items):
        ln = struct.unpack_from('<i', dec, off)[0]; off += 4
        if not (0 <= ln <= 256) or off + ln + 3 > len(dec):
            raise ValueError('cell_item lỗi')
        name = dec[off:off + ln].split(b'\0')[0].decode('cp949', 'replace'); off += ln
        cx, cy, chance = struct.unpack_from('<3B', dec, off); off += 3
        cell_items.append({'name': name, 'x': cx, 'y': cy, 'chance': chance})
    info['cell_items'] = cell_items
    # 2. Đường tuần tra (patrol_paths)
    n_paths = struct.unpack_from('<i', dec, off)[0]; off += 4
    if not (0 <= n_paths <= 5000):
        raise ValueError('n_paths không hợp lệ: %d' % n_paths)
    paths = []
    for _ in range(n_paths):
        plen = struct.unpack_from('<i', dec, off)[0]; off += 4
        if not (0 <= plen <= 5000) or off + 8 * plen > len(dec):
            raise ValueError('path lỗi')
        pts = [list(struct.unpack_from('<2i', dec, off + 8 * k)) for k in range(plen)]
        off += 8 * plen
        paths.append(pts)
    info['patrol_paths'] = paths
    # 3. Quái đặt sẵn (placed_monsters)
    n_mons = struct.unpack_from('<i', dec, off)[0]; off += 4
    if not (0 <= n_mons <= 5000):
        raise ValueError('n_mons không hợp lệ: %d' % n_mons)
    mons = []
    for _ in range(n_mons):
        ln = struct.unpack_from('<i', dec, off)[0]; off += 4
        if not (0 <= ln <= 256) or off + ln + 14 > len(dec):
            raise ValueError('mon lỗi')
        name = dec[off:off + ln].split(b'\0')[0].decode('cp949', 'replace'); off += ln
        mdata = list(struct.unpack_from('<14B', dec, off)); off += 14
        mons.append({'name': name, 'params': mdata})
    info['placed_monsters'] = mons
    # 4. Script XML cuối file (v30)
    script_len = struct.unpack_from('<i', dec, off)[0]; off += 4
    if off + script_len != len(dec):
        raise ValueError('lệch cuối file: off=%d + script_len=%d != len=%d' % (off, script_len, len(dec)))
    script_xml = dec[off:off + script_len].decode('cp949', 'replace').lstrip('\r\n') if script_len > 0 else ''
    if script_xml:
        info['script_xml'] = script_xml
    bgm_info = resolve_bgm(map_name, script_xml)
    info['bgm'] = bgm_info['bgm']
    info['bgm_info'] = bgm_info
    return info


def ascii_map(info):
    lines = []
    for y, row in enumerate(info['grid']):
        lines.append(' '.join('%5s' % ('.' if c['object'] == -1 else c['object']) for c in row))
    return '\n'.join(lines)


def batch(root):
    ok, bad = 0, []
    for dp, _, fs in sorted(os.walk(root)):
        if 'raw.bin' not in fs:
            continue
        mname = os.path.basename(dp)
        try:
            data = open(os.path.join(dp, 'raw.bin'), 'rb').read()
            mask = guess_mask(data)
            dec = decrypt(data, mask)
            info = parse(dec, mname)
            info['mask'] = mask
            json.dump(info, open(os.path.join(dp, 'map.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            if 'script_xml' in info:
                open(os.path.join(dp, 'script.xml'), 'w', encoding='utf-8', newline='').write(info['script_xml'])
            ok += 1
            print('OK   %-32s v%-4d %3dx%-3d bgm=%s' % (mname, info['version'], info['cols'], info['rows'], info['bgm']))
        except Exception as e:
            bad.append((mname, str(e)))
            print('LỖI  %-32s %s' % (mname, e))
    print('\nXong: %d thành công, %d lỗi' % (ok, len(bad)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('file', nargs='?')
    ap.add_argument('--batch', help='thư mục gốc, vd AssetsDecoded/fx/Map')
    ap.add_argument('-o', '--json')
    ap.add_argument('--dec', help='ghi bản giải mã thô')
    ap.add_argument('--mask', type=lambda s: int(s, 0))
    a = ap.parse_args()
    if a.batch:
        sys.exit(batch(a.batch))
    if not a.file:
        ap.error('cần file hoặc --batch')
    data = open(a.file, 'rb').read()
    mask = a.mask if a.mask is not None else guess_mask(data)
    dec = decrypt(data, mask)
    print('mask = 0x%08X, %d byte' % (mask, len(dec)))
    if a.dec:
        open(a.dec, 'wb').write(dec)
    mname = os.path.basename(os.path.dirname(os.path.abspath(a.file)))
    info = parse(dec, mname)
    print('version %d  lưới %dx%d  bgm: %s' % (info['version'], info['cols'], info['rows'], info['bgm']))
    print('Lớp vật thể (object id, . = trống):')
    print(ascii_map(info))
    if a.json:
        json.dump(info, open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
