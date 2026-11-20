# CGOBomb (bóng nước) – ghi chú trích từ CA.exe.c (bản repo kaze170/BnB_TW_22)

Mức tin cậy: **[X]** thấy trực tiếp trong code, **[S]** suy luận từ cách dùng, **[?]** chưa biết.
Địa chỉ dạng `sub_XXXXXX`. Các hàm `sub_43827E` (đọc) / `sub_437FB8` (ghi) là "số nguyên được bảo vệ chống cheat" (mỗi trường chiếm 12 byte, XOR ngẫu nhiên); khi viết lại chỉ cần dùng int thường.

## 1. Vị trí trong cây class
- `CGOBomb` kế thừa `CGameObject` và `CSensorTrigger` (hai vftable tại offset 0 và +80) **[X]** (dòng 4188–4192, `CSensorTrigger::possible_ctor_or_dtor_0` khởi tạo `CGOBomb`).
- Họ gần: `CGOSealBomb`, `CGOBombSprinkler`, `CBombOwner`, `CMapActionBomb`, `CBombDecoMan`.
- Chỉ có **6 hàm** mang tên `CGOBomb::`, phần lớn logic nằm ở hàm không tên (`sub_44xxxx`). Logic **nổ, lan tia nổ, tính sát thương không nằm trong CGOBomb** mà ở bản đồ/`CMapAction*` (chưa đọc) **[S]**.

## 2. Asset / sprite
- Sprite mặc định khi khởi tạo: `"Bomb/Bomb"` (`CGameObject::sub_4409CA(this, "Bomb/Bomb")`) **[X]**.
- Tên sprite tùy biến ghép từ chuỗi: `"Bomb%03d"` (sub_443625), `"BombDeco/%s"`, `"ObjectTable/%s"` **[X]**; nếu không tìm thấy sprite tùy biến thì quay về `"Bomb/Bomb"` **[X]**. Nghĩa là: skin bóng nước (BombDeco) tra theo id → tên, rồi dùng sprite đó, không có thì dùng mặc định.
- Trạng thái → frame: chưa thấy trong `CGOBomb`; nhiều khả năng dùng `ObjectTable` (state + frames) giống các object khác **[?]**.

## 3. Hệ tọa độ (quan trọng cho việc vẽ)
- Ô 40×40 px; lưới tối đa **13 hàng × 15 cột** (kiểm tra `n0xC <= 0xC`, `n0xE <= 0xE`) **[X]**.
- Vị trí vật thể đặt bằng `SetPos(40*col, 40*row + 39)` (hàm ảo +96) **[X]** (CGOBomb::sub_443339, sub_4423C8, sub_442BF1). ⇒ **điểm neo của đối tượng = góc dưới-trái của ô** (y = đáy ô, x = mép trái).
- Với kiểu vẽ `top-left = neo − offset` (offset là hotspot trong frame), sprite cao hơn ô sẽ mọc lên phía trên ô – khớp với cách agent Godot đang làm (neo đáy-trái, trừ offset) **[S]**. Chưa kiểm chứng bằng hình.
- Bản đồ **cuộn vòng**: khi tọa độ ô vượt biên thì cộng/trừ số hàng/cột (sub_442FF7) **[X]**.

## 4. Chuyển động bóng (đá/ném/trượt)
- Tia di chuyển dùng bảng hướng `dword_91D7BC[2*dir]` (dRow) và `n2[2*dir]` (dCol), 4 hướng **[X]** (bảng nằm trong exe, chưa trích).
- `sub_442FF7` (ném): quét tối đa 6 ô theo hướng, tìm ô đáp, cộng dồn thời gian bay: `+75/ô`, `+360`, `+120/ô`, `+200` (ms) **[X]** (ý nghĩa chính xác **[S]**).
- Hiệu ứng nảy khi đứng yên: độ cao `960*(7.5−|phase−7|)²/225` (phase 0..14) **[X]**.
- Cung ném 15 bước: `y_off = 960*(t−15)²/225`, t = 0..15 **[X]** (CGOBomb::sub_443339).
- `sub_442BF1` = bước cập nhật khi bóng đang trượt/bị đá, máy trạng thái pha `this+73` ∈ {0,1,2,3,4} dùng 4 bảng dữ liệu (`dword_9150C0…`) **[X]**; bảng chưa trích **[?]**. Pha 4 + canh đúng ô ⇒ dừng, đặt lại vào lưới **[X]**.
- Cờ trạng thái chính: `this+95` ∈ {0,1,2} (1 hoặc 2 ⇒ không kích hoạt cảm biến) **[X]**; ý nghĩa từng giá trị **[?]**.

## 5. Âm thanh
- Game giữ **bảng ID âm thanh** trong exe (143 mục, địa chỉ ảo 0x917F70, `off_917F70` trong CA.exe.c). Đã trích ra `sound_table.json`. Ví dụ: `0 BomberWalk`, `1 BombExplode`, `2 BombIgnite`, `75 SprinklerBomb`, `68 TimebombExplode`, `111 M_SealBomb` **[X]**.
- Ghép sự kiện → âm thanh là **theo ID** qua trình quản lý âm thanh toàn cục (`CSoundMan`, `sub_66A9C0()` trả về đối tượng) **[X]**. Ngoài ra có kiểu ghép theo tên: chuỗi `"Wave/%s"` từ tên đối tượng, kiểm tra file tồn tại trong pack trước khi phát **[X]** (dòng 98195, 102901).
- Chưa tìm ra hàm phát âm (`sub_66AA70` là hàm **dừng** theo ID) nên chưa biết **bóng nước gọi ID nào lúc nào** (đoán: ignite = 2 khi đặt, explode = 1 khi nổ) **[?]**.

## 6. Việc chưa làm / bước tiếp theo
1. Tìm hàm phát âm của `CSoundMan` (các hàm 0x66AAD0–0x66B3xx) rồi tìm chỗ gọi với ID 1 và 2 để xác nhận.
2. Đọc `CMapActionBomb` và hàm nổ trong lớp bản đồ để lấy: thời gian đếm ngược, cách tính tầm nổ, phản ứng dây chuyền, ô bị phá.
3. Trích các bảng dữ liệu trong exe: `dword_91D7BC`, `n2`, `dword_9150C0…9151F8`.
4. Giải `Attr/BomberAttr` (bằng `ca_pack_tool.py`) để lấy số liệu cơ bản (tầm nổ, số bóng, tốc độ).
5. Viết class GDScript sau khi có 1–4 (tránh viết bản đoán).
