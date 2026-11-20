#!/usr/bin/env python3
"""Tra cứu nhanh (rẻ token), dựa trên index.json.
    fn.py body  <tên|sub_XXXX> [maxdòng=150]   in thân hàm + callee
    fn.py who   <tên>                          ai gọi hàm này
    fn.py str   <aXxx>                         hàm nào dùng chuỗi này
    fn.py cls   <Lớp>                          liệt kê method (vftable, ctor...) của lớp
    fn.py find  <regex>                        tìm tên hàm/chữ ký khớp
"""
import json, os, re, sys, itertools
H = os.path.dirname(os.path.abspath(__file__))
I = json.load(open(os.path.join(H, os.environ.get("IDX","index.json"))))
F, SRC = I['funcs'], os.path.normpath(os.path.join(H, I['src']))
def pick(n):
    if n in F: return F[n]
    c = [k for k in F if k.split('#')[0] == n]
    return F[c[0]] if c else None
cmd, a = sys.argv[1], sys.argv[2]
if cmd == 'body':
    mx = int(sys.argv[3]) if len(sys.argv) > 3 else 150
    f = pick(a) or sys.exit('không thấy ' + a)
    print(f"// {f['name']} dòng {f['start']}-{f['end']} ({f['end']-f['start']+1} dòng)")
    with open(SRC, encoding='latin1') as fh:
        for ln in itertools.islice(fh, f['start'] - 1, min(f['end'], f['start'] - 1 + mx)): print(ln, end='')
    if f['end'] - f['start'] + 1 > mx: print(f'// ... cắt, còn {f["end"]-f["start"]+1-mx} dòng')
    print('// calls:', ' '.join(f['calls'][:40]))
    print('// strs :', ' '.join(f['strs'][:40]))
elif cmd == 'who': print('\n'.join(I['callers'].get(a, [])[:60]) or 'không có')
elif cmd == 'str': print('\n'.join(I['strx'].get(a, [])[:60]) or 'không có')
elif cmd == 'cls':
    for k, v in F.items():
        if a + '::' in v['sig'] or k.startswith(a + '::'): print(k, v['start'], v['end'] - v['start'] + 1)
elif cmd == 'find':
    r = re.compile(a)
    for k, v in F.items():
        if r.search(v['sig']): print(k, v['start'], v['end'] - v['start'] + 1, '|', v['sig'][:90])
