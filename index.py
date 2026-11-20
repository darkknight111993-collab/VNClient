#!/usr/bin/env python3
"""Lập chỉ mục file Hex-Rays (.c) một lần: hàm -> dòng, callee, chuỗi (aXxx), caller.
    python3 -I index.py ../ca.exe.a.c index.json
"""
import json, re, sys, collections
src, out = sys.argv[1], sys.argv[2]
SIG = re.compile(r'^[A-Za-z_][^;=]*?([A-Za-z_~][\w:~`<>]*)\(')
CALL = re.compile(r'\b(sub_[0-9A-Fa-f]+|[A-Z]\w*::[\w~]+)\b')
STR = re.compile(r'\b(a[A-Z]\w{2,})\b')
funcs, prev, cur = {}, '', None
with open(src, encoding='latin1') as f:
    for n, line in enumerate(f, 1):
        if cur is None:
            if line.startswith('{') and prev and not prev.startswith(('//', ' ')):
                m = SIG.match(prev)
                if m:
                    name = m.group(1)
                    if name in funcs: name = f'{name}#{n}'
                    cur = {'name': name, 'start': n - 1, 'sig': prev.strip()[:160], 'calls': set(), 'strs': set()}
            prev = line.rstrip('\n')
        else:
            if line.startswith('}'):
                cur['end'] = n
                funcs[cur['name']] = cur
                cur = None
                prev = ''
                continue
            for c in CALL.findall(line): cur['calls'].add(c)
            for s in STR.findall(line): cur['strs'].add(s)
callers, strx = collections.defaultdict(list), collections.defaultdict(list)
for k, v in funcs.items():
    for c in v['calls']: callers[c].append(k)
    for s in v['strs']: strx[s].append(k)
for v in funcs.values():
    v['calls'] = sorted(v['calls']); v['strs'] = sorted(v['strs'])
json.dump({'src': src, 'funcs': funcs, 'callers': callers, 'strx': strx}, open(out, 'w'))
print(len(funcs), 'hàm,', len(strx), 'chuỗi ->', out)
