# Công cụ tra cứu decompile (rẻ token)
Agent KHÔNG đọc trực tiếp `ca.exe.a.c` (36 MB) / `Converter/CA.exe.c`. Dùng:

    python3 -I index.py ../ca.exe.a.c index.json            # 1 lần, ~2s
    python3 -I index.py ../Converter/CA.exe.c index_ca.json
    python3 -I fn.py body <hàm> [maxdòng]   # thân hàm + callee + chuỗi
    python3 -I fn.py who  <hàm>             # caller (trực tiếp, không qua vtable)
    python3 -I fn.py str  <aXxx>            # hàm dùng chuỗi
    python3 -I fn.py cls  <Lớp>             # method của lớp
    python3 -I fn.py find <regex>           # tìm theo chữ ký
    IDX=index_ca.json python3 -I fn.py ...  # chọn chỉ mục khác

Mẹo: `Converter/CA.exe.c` có tên lớp/method (CGOTile*, CGOBomb::...) nên dễ lần hơn
`ca.exe.a.c` (toàn sub_XXXX). Lọc dòng khai báo biến bằng grep -v để giảm token.
Giới hạn: gọi qua vtable (`(*(this+84))(...)`) không có trong call graph.
