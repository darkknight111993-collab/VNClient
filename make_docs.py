#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# make_docs.py — Quét file decompile Hex-Rays (ca.exe.c) -> ca_docs.json
# Chạy:  python make_docs.py ca.exe.c ca_docs.json     (chỉ dùng thư viện chuẩn)
import json, os, re, sys
from collections import Counter, defaultdict

SRC = sys.argv[1] if len(sys.argv) > 1 else "ca.exe.c"
DST = sys.argv[2] if len(sys.argv) > 2 else "ca_docs.json"

RE_HEAD = re.compile(r'^[A-Za-z_][^;{}=]*?\b(sub_[0-9A-Fa-f]+|nullsub_\d+|'
                     r'[A-Za-z_]\w*(?:::[~A-Za-z_]\w*)+|start|WinMain|wWinMain|main|DllMain)\s*\(')
RE_CALL = re.compile(r'\b(sub_[0-9A-Fa-f]+|nullsub_\d+)\s*\(')
RE_GLOB = re.compile(r'\b(?:off|dword|qword|word|byte|flt|dbl|unk|asc|str|xmmword)_[0-9A-Fa-f]{4,}\b')
RE_STR  = re.compile(r'\ba[A-Z][A-Za-z0-9_]{2,}\b')
RE_VFT  = re.compile(r"([^\s&=*(),;]+)::`vftable'")
RE_RTTI = re.compile(r'\b_TI\d[\w@]*\b')
CCS = ("__thiscall", "__fastcall", "__stdcall", "__cdecl", "__usercall", "__userpurge")

KNOWN = {  # chú thích thủ công, địa chỉ chỉ đúng ca.exe.c gốc
 "sub_9DBE57": "malloc / cấp phát bộ nhớ thô (nền của operator new)",
 "sub_9DADB6": "free / operator delete — giải phóng bộ nhớ",
 "sub_9DB760": "memcpy/memmove — copy n byte",
 "sub_9DBAD0": "memmove — dịch chuyển n byte (vùng nhớ chồng lấp)",
 "sub_9DB6D0": "strlen — độ dài chuỗi C",
 "sub_9DBED7": "_CxxThrowException — ném ngoại lệ C++ (object + RTTI)",
 "sub_9DAE5A": "ctor họ std::exception (khởi tạo message)",
 "sub_9DAEB6": "dtor họ std::exception",
 "sub_9D84E9": "std::_Xlen(msg) — ném length_error",
 "sub_9D8536": "std::_Xran(msg) — ném out_of_range",
 "sub_9DC22B": "helper chia 64-bit lấy thương + dư (kiểu _alldvrm)",
 "sub_9DB5CB": "helper CRT cuối hàm có EH unwind (nghi security cookie/dọn frame)",
}
CONSTS = {"0xfffffff": "max_size() vector phần tử 16 byte (2^28-1)",
          "0x3fffffff": "max_size() vector phần tử 4 byte (2^30-1)",
          "97612893": "max_size() container phần tử 44 byte (0x5D1745D)",
          "0x4ec4ec4": "giới hạn số phần tử 52 byte"}
SPECIAL_G = {
 "off_C10510": "vtable họ std::exception/std::bad_alloc (có thể bị COMDAT folding)",
 "dword_C10540": "chuỗi C mặc định cho ctor std::string — gần như chắc chắn là \"\"",
 "flt_C10674": "hằng số float 2^32 (4294967296.0) — hiệu chỉnh int âm -> double unsigned",
 "aStringTooLong": 'chuỗi "string too long" (length_error của std::string)',
 "aInvalidStringP": 'chuỗi "invalid string position" (out_of_range của std::string)',
 "aVectorTTooLong": 'chuỗi "vector<T> too long"',
 "aListTTooLong": 'chuỗi "list<T> too long"',
 "aCspecialtileat": 'chuỗi "CSpecialTileAt..." — nghi tên lớp CSpecialTileAttrList',
}

def split_params(s):
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch == "," and depth == 0:
            out.append(cur.strip()); cur = ""
        else:
            if ch in "(<": depth += 1
            elif ch in ")>": depth -= 1
            cur += ch
    if cur.strip(): out.append(cur.strip())
    return out

def param_info(p):
    if p in ("void", ""): return None
    if "(*" in p:
        m = re.search(r'\*+\s*([A-Za-z_]\w*)\s*\)', p)
        name = m.group(1) if m else "?"
    else:
        ids = re.findall(r'[A-Za-z_]\w*', p)
        name = ids[-1] if ids else "?"
    return {"ten": name, "khai_bao": p}

def classify(name, sig, b, attr, callees, strs, vfts):
    if name in KNOWN: return ("helper CRT/boost", KNOWN[name], "trung bình")
    if name.startswith("nullsub") or b in (";", ""):
        return ("noop", "Hàm rỗng (no-op) — virtual placeholder hoặc bị tối ưu rỗng.", "cao")
    if "thunk" in attr:
        return ("thunk", "Chuyển tiếp (thunk) tới " + (callees[0] if callees else "?"), "cao")
    if re.fullmatch(r"return this;", b):
        return ("identity", "return this — ctor/copy-ctor mặc định hoặc virtual không làm gì.", "cao")
    cm = re.fullmatch(r"return\s+(-?(?:0x[0-9A-Fa-f]+|\d+));", b)
    if cm:
        v = cm.group(1); extra = CONSTS.get(v.lower(), "")
        return ("const", "Trả về hằng số " + v + (". " + extra if extra else ". Chưa rõ nghĩa — cần ngữ cảnh caller."),
                "cao" if extra else "trung bình")
    if re.fullmatch(r"return\s+(this\[\d+\]|\*this|\*\(_DWORD \*\)this)\s*;", b):
        return ("getter", "Getter — trả về một trường của object (" + b[7:-1] + ").", "cao")
    if re.fullmatch(r"(?:return\s+)?(?:sub_[0-9A-Fa-f]+|nullsub_\d+)\s*\([^;]*\)\s*;", b, re.S):
        return ("wrapper", "Bọc/gọi thẳng tới " + (callees[0] if callees else "?") + " (construct/_Ucopy/adapter).", "cao")
    if "__noreturn" in sig:
        if any("TooLong" in s for s in strs):
            return ("exception", "Ném std::length_error — thông báo: " + ", ".join(strs), "cao")
        if any("InvalidString" in s for s in strs):
            return ("exception", "Ném std::out_of_range — thông báo: " + ", ".join(strs), "cao")
        return ("exception", "Hàm không trả về — ném ngoại lệ/abort.", "trung bình")
    if "bad_alloc" in b:
        em = re.search(r'\(\s*(\d+)\s*\*\s*a1\s*\)', b)
        sz = em.group(1) if em else "1"
        return ("allocator", "Cấp phát mảng phần tử %s byte (operator new/_Allocate); thất bại ném std::bad_alloc." % sz, "cao")
    if "_InterlockedExchangeAdd" in b:
        return ("shared_ptr", "boost sp_counted_base::release — giảm refcount nguyên tử; hết mạnh -> dispose, hết yếu -> destroy.", "cao")
    if vfts:
        if re.search(r"a2 & 1", b):
            return ("dtor", "Scalar deleting destructor — gán vtable %s, cờ bit0=1 thì free object." % ", ".join(vfts), "cao")
        return ("ctor/dtor", "Gán vtable %s — constructor/destructor của lớp tương ứng." % ", ".join(vfts), "cao")
    if "16807" in b:
        return ("RNG", "Bước sinh số ngẫu nhiên minstd (Park-Miller): X = 16807*X mod 2^31-1 (Schrage).", "cao")
    if re.search(r"(this|a1)\[5\]", b) and "0x10" in b:
        return ("std::string", "Thao tác std::string MSVC (SSO 16B): this[0..3]=buffer/ptr, this[4]=size, this[5]=capacity.", "cao")
    if re.search(r"\(this\[2\] - \*this\)", b):
        elem = "16" if ">> 4" in b else ("44" if "/ 44" in b else "4")
        return ("std::vector", "Thao tác std::vector phần tử %s byte (this[0]=begin, [1]=end, [2]=cap) — reserve/insert/growth." % elem, "cao")
    if "this[8]" in b and "this[9]" in b:
        return ("hash table", "Bảng băm stdext::hash_*: this[8]=mask, this[9]=số bucket — chỉ số bucket/load factor.", "trung bình")
    if re.search(r"sub_[0-9A-Fa-f]+\(\s*52\s*\)", b):
        return ("std::list", "Thao tác std::list — node 52B = 2 con trỏ link + value 44B.", "trung bình")
    return ("chưa phân loại", "Hàm logic của client — xem goi_den/chuỗi tham chiếu; dùng fn.py who/body để lấy ngữ cảnh.", "thấp")

def build_entry(name, sig, body, attr):
    m = re.match(r'^(.*?)\b' + re.escape(name) + r'\s*\((.*)\)\s*$', sig, re.S)
    head, praw = (m.group(1), m.group(2)) if m else (sig, "")
    cc = next((c for c in CCS if c in head), "?")
    params = [p for p in (param_info(x) for x in split_params(praw)) if p]
    locals_ = []
    for ln in body.splitlines():
        s = ln.strip()
        if not s: continue
        dm = re.match(r'^(.+?);\s*//\s*(.+)$', s)
        if dm and ln.startswith((" ", "\t")) and "=" not in dm.group(1):
            decl, loc = dm.group(1).strip(), dm.group(2).strip()
            if "(" in decl and "(*" not in decl: break
            nm = (re.search(r'\*+\s*(\w+)\s*\)', decl) if "(*" in decl
                  else re.search(r'([A-Za-z_]\w*)\s*(\[[^\]]*\])?$', decl))
            locals_.append({"ten": nm.group(1) if nm else decl, "khai_bao": decl,
                            "vi_tri": loc, "byref": "BYREF" in loc})
        else:
            break
    callees = sorted(set(RE_CALL.findall(body)) - {name})
    globs = sorted(set(RE_GLOB.findall(body)))
    strs  = sorted(set(RE_STR.findall(body)))
    vfts  = sorted(set(RE_VFT.findall(body)))
    rtti  = sorted(set(RE_RTTI.findall(body)))
    cat, desc, conf = classify(name, sig, body.strip(), attr, callees, strs, vfts)
    return {"ten": name,
            "dia_chi": ("0x" + name[4:]) if name.startswith("sub_") else None,
            "chu_ky": " ".join(sig.split()), "quy_uoc_goi": cc,
            "noreturn": "__noreturn" in head, "thunk": "thunk" in attr,
            "tham_so": params, "bien_cuc_bo": locals_, "goi_den": callees,
            "chu_thich_helper": {c: KNOWN[c] for c in callees if c in KNOWN},
            "bien_toan_cuc_tham_chieu": globs, "chuoi_tham_chieu": strs,
            "vtable_tham_chieu": vfts, "rtti_tham_chieu": rtti,
            "co_goi_gian_tiep_vtable": bool(re.search(r'\(\s*\*', body)),
            "phan_loai": cat, "chuc_nang": desc, "do_tin_cay": conf}

def global_desc(g):
    if g in SPECIAL_G: return SPECIAL_G[g]
    if g.endswith("::`vftable'"): return "Bảng hàm ảo (vtable) của lớp " + g[:-11]
    if g.startswith("_TI"): return "RTTI Type Descriptor (dùng khi ném/bắt ngoại lệ C++)."
    if re.match(r'^a[A-Z]', g): return "Chuỗi literal C (tên Hex-Rays đặt theo nội dung, đã cắt gọn)."
    pre = g.split("_")[0]
    return {"off": "Con trỏ 4 byte — thường là vtable/RTTI/con trỏ hàm.",
            "flt": "Hằng số float.", "dbl": "Hằng số double.",
            "dword": "Biến 4 byte.", "word": "Biến 2 byte.", "byte": "Biến 1 byte.",
            "qword": "Biến 8 byte."}.get(pre, "Dữ liệu toàn cục chưa định kiểu.")

def main():
    with open(SRC, "r", encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    funcs, i, n, attr = [], 0, len(lines), ""
    while i < n:
        line = lines[i]
        if line.startswith("// attributes:"):
            attr = line; i += 1; continue
        m = RE_HEAD.match(line)
        if not m:
            if line.strip() and not line.startswith((" ", "\t", "/", "#", "}")): attr = ""
            i += 1; continue
        name, sig, j = m.group(1), line, i
        while sig.count("(") > sig.count(")") and j + 1 < n:
            j += 1; sig += " " + lines[j].strip()
        k = j + 1
        while k < n and not lines[k].strip(): k += 1
        if k >= n or lines[k].strip() != "{":
            attr = ""; i = j + 1; continue
        body, j = [], k + 1
        while j < n and lines[j].rstrip() != "}":
            body.append(lines[j]); j += 1
        funcs.append(build_entry(name, sig, "\n".join(body), attr))
        attr = ""; i = j + 1
    gref = defaultdict(list)
    for f in funcs:
        for g in (f["bien_toan_cuc_tham_chieu"] + f["chuoi_tham_chieu"] + f["rtti_tham_chieu"]
                  + [v + "::`vftable'" for v in f["vtable_tham_chieu"]]):
            gref[g].append(f["ten"])
    globals_ = [{"ten": g, "chuc_nang": global_desc(g), "so_ham_tham_chieu": len(refs),
                 "ham_tham_chieu": refs[:30]} for g, refs in sorted(gref.items())]
    out = {"meta": {"file": SRC, "kich_thuoc_byte": os.path.getsize(SRC),
                    "cong_cu_goc": "Hex-Rays 9.1 (IDA), Visual C++ 32-bit",
                    "luu_y": ["Mô tả sinh bằng heuristic — xem do_tin_cay từng hàm.",
                              "Gọi qua vtable không có trong goi_den (co_goi_gian_tiep_vtable=true nếu có)."]},
           "thong_ke": {"tong_ham": len(funcs),
                        "theo_phan_loai": dict(Counter(f["phan_loai"] for f in funcs)),
                        "tong_bien_toan_cuc_chuoi_vtable": len(globals_),
                        "so_ham_goi_vtable": sum(f["co_goi_gian_tiep_vtable"] for f in funcs)},
           "ham": funcs, "bien_toan_cuc_va_hang": globals_}
    with open(DST, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("OK: %d hàm, %d biến/chuỗi/vtable -> %s" % (len(funcs), len(globals_), DST))
    print(dict(Counter(f["phan_loai"] for f in funcs)))

if __name__ == "__main__":
    main()