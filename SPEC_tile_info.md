# tile_info.xml / CMapObjToTileInfo (đã xác minh từ code)
Loader: ca.exe.a.c `sub_977FFB` (CA.exe.c: `sub_5A36C0`→ "TileInfo/TileInfoList").
`<Tile Name="..." Data="hex">` → giải hex = **52 byte**, cất vào map theo Name.
Singleton `CMapObjToTileInfo` (global dword_E63F64), tạo ở `sub_97829D`.
Log dump: `sub_9779EB` (ghi MapTileLog.txt) → nguồn layout. Offset trong log = offset Data + 4.

Data[0..3] = tileType (u32): 0 Ground, 1 Static, 2 Box, 3 Passable, 4 Decorator (theo file: 1254/1678/285/145/7).

| type | trường (offset Data) |
|---|---|
| 0 Ground | u32@4,@8,@12,@16,@20,@24,@28,@32,@36 ; u8@40 ; i16@42 |
| 1 Static | i32@4,@8,@12,@16 ; u8@20..@24 ; i32@28..@48 |
| 2 Box | i32@4,@8 ; u8@12 ; u8@13 ; i16@14 |
| 3 Passable | u8 x16 @4..@19 (cờ 0/1, nhiều khả năng mặt nạ đi được 16 ô con); i32@24,@28,@32,@36 (giá trị giống con trỏ runtime, bỏ qua) |
| 4 Decorator | không có trường |

PinTile01 / PinGround01 (type 3 / 0): KHÔNG có byte nào mang nghĩa "bom nổ khi rơi vào".
Không có chuỗi "Pin" trong ca.exe.a.c → hành vi chông (nếu có) không nằm trong tile_info.
Chưa xác minh: ý nghĩa chính xác từng byte cờ; logic bom↔tile (`CGOBomb::sub_443339`, 105 dòng, gọi map qua sub_43D325).

# Lớp tile (Converter/CA.exe.c)
CGOTile → CGOTileFixed → {Ground, Static, Passable, Box(Fixed/Movable), Lap, StaticLucci, StaticReactive}.
- CGOTilePassable::sub_45EAA6 (dòng 108594): mỗi frame, duyệt 8 người chơi; ô = ((x-15)/40, (y+20)/40) → đổi trạng thái tile khi có người đứng trên (kiểu mái nhà/lều mờ đi). Không liên quan bom.
- CGOTileStaticReactive::sub_5F2B61 (dòng 463451): máy trạng thái animation (idle ngẫu nhiên / phản ứng / trigger). Cosmetic.
