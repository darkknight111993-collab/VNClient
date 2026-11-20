# BnB / Crazy Arcade → Godot 4 Converter – Plan

Goal: **one command** converts everything in `ExtractedAssets/` into `AssetsDecoded/`.
Every source file becomes **a folder** with the same relative path/name, containing the Godot‑importable outputs (PNG, OGG, JSON, ...).

```
python Converter/convert.py            # converts all, parallel, resumable
python Converter/convert.py --only fx/MP3 --force   # optional filters
```

## 0. Findings from inspecting the input (22,610 files, 4 archives)

| Archive | Files | Notes |
|---|---|---|
| `charte` | 3,695 | avatar/char decorations, icons, bomb deco |
| `emote` | 5,457 | emotes, fanfare sounds (`Wave`) |
| `fx` | ~12,900 | UI, tiles, maps, monsters, `MP3`, `Wave`, `XML`, ... |
| `fxasset` | 11 | avatar deco + object table |

Each archive has `manifest.json` (archive, path, offset, size, sha1 per file). Extracted files have **no extension**, so type is detected by **magic bytes**:

| Kind | Detection | Count (approx.) | Output |
|---|---|---|---|
| **A. Proprietary sprite** | `u32 nFrameGroups, u32 = 2, u32 n, ...` (e.g. `01000000 02000000 01000000`) | majority (~15k+) | `frame_0000.png …` + `sprite.json` (frame offsets, sizes, anchors, timing) + optional `spritesheet.png` and `.tres` SpriteFrames |
| **B. JPEG** | `FF D8 FF` (CAStage, backgrounds) | ~20 | `image.jpg` (+ `image.png`) |
| **C. Ogg Vorbis sound** | `OggS` (`fx/MP3`, `fx/Wave`, `emote/Wave`) | ~700 | `sound.ogg` (Godot imports natively) |
| **D. Plain text/XML** | starts with `<` / BOM / text (`XML`, `ClientData`, `TileInfo`, `Help`) | few | `data.xml`/`data.txt` (UTF‑8 converted from CP949/UTF‑16) + `data.json` |
| **E. `PACK0001` container** | magic `PACK0001` (`charte/IDDX`) | 12 | zlib stream inside → unpacked files |
| **F. zlib‑wrapped** | `u32 rawSize, u32 compSize, 78 DA` (`fx/Etc`) | 1,170 | decompressed, then re‑classified (A–D) recursively |
| **G. Encrypted tables** | no known magic, high entropy (`ObjectTable`, `Map`, `MapScriptTemplate`, `Attr`, `NameTable`, `*ObjectTable`) | ~1,500 | decrypt → decompress → text/binary → `data.json` |
| **H. Manifests** | `manifest.json` | 4 | copied as `manifest.json` into `AssetsDecoded/<archive>/` |

> [!WARNING]
> Kinds **A** (sprite pixel encoding) and **G** (the cipher on Map/ObjectTable) are proprietary and **undocumented**.
> I must reverse‑engineer them. Already visible: G files share repeating key‑like bytes (`71 9c`, `1e f2`, `e3 1b 9c` …) → likely a simple XOR/byte‑substitution stream cipher. A uses a header + RLE‑style pixel stream (`c0 70 a5 5c 00 70 a5 5c …`). These are the two risky steps; each is validated (see step 9).

## Step by step

1. **Scan** – read the 4 `manifest.json`, walk `ExtractedAssets`, build a work list (`archive/path`), skip `manifest.json` from content processing.
2. **Detect type** – `detect.py` reads first 16–32 bytes and returns A–G (magic first, then entropy/text heuristics, then "unknown").
3. **Output layout** – for each file `ExtractedAssets/<archive>/<dir>/<Name>` create `AssetsDecoded/<archive>/<dir>/<Name>/` (folder, same name; never collides with siblings). Always write `meta.json` (source path, sha1, detected type, converter version, warnings).
4. **Simple converters first** (C, B, D): copy/rename to `.ogg`/`.jpg`, re‑encode text to UTF‑8 + `.json`.
5. **Container/compression layer** (E, F): `PACK0001` parser + zlib; result bytes are fed back to step 2 (recursive, depth‑limited).
6. **Sprite decoder (A)** – reverse‑engineer header (frame groups, per‑frame x/y/w/h, offsets, delay) and pixel stream; palette/colour‑key (`ff ff ff ff` marker) → RGBA. Output per‑frame PNGs, packed `spritesheet.png`, `sprite.json`, and a generated Godot `SpriteFrames` `.tres` for animated ones.
7. **Cipher/table decoder (G)** – find the key/algorithm using known plaintext (the `.xml` files and other files with known XML structure), decrypt, parse to JSON.
8. **Runner** – `convert.py` uses `multiprocessing` (all cores), progress bar, error isolation (one bad file never stops the run; failures logged to `AssetsDecoded/_report.json` and `_errors.log`), resumable (skips if `meta.json` hash matches; `--force` to redo).
9. **Validation** – self‑check per file: PNG size == header size, Ogg opens, JSON parses; final report: counts per type, % converted, unknown list. Spot check by viewing sample PNGs.
10. **Godot 4 import** – outputs placed under `AssetsDecoded/`; copy/point the Godot project there (`res://AssetsDecoded/...`). Add `.gdignore` not needed. PNG/OGG/JPG import automatically; `.tres` SpriteFrames load directly; JSON via `JSON.parse_string`.

## Deliverables
- `Converter/convert.py` (entry), `detect.py`, `sprite.py`, `crypt.py`, `containers.py`, `godot.py`
- `AssetsDecoded/<archive>/<path>/<Name>/…` + `_report.json`

## Open questions
1. OK to proceed knowing that the sprite & encrypted‑table formats need reverse engineering (may not reach 100% on first pass)?
2. Sprite output: PNG frames only, or also `SpriteFrames .tres` + spritesheet? (default: all three)
3. Keep original raw file as `raw.bin` inside each folder? (default: no, saves ~size of assets)

## Status (implemented)
`python Converter/convert.py` converts all 22,610 files (~10 min, 12 workers, resumable, `--force`, `--only`, `--limit`, `--workers`).

| Result | Count |
|---|---|
| sprite → PNG images + cropped frames + `sprite.json` + `frames.tres` | 20,434 |
| ogg → `sound.ogg` | 645 |
| jpeg → `image.jpg` | 63 |
| text/xml → UTF-8 `data.xml/txt` | 13 |
| PACK0001 → `entry_NN/` sprites (+`tail.bin`) | 12 |
| **unsupported (raw.bin kept)** | **1,443** |

Sprite format (reverse engineered): 16-byte header `[frames, 2, images, X]`, `(h,w)` per image, 48-byte frame records
`[ox,oy,flag,image,x0,y0,x1,y1,+4]`, then per image `[size][RLE]`. RLE ops: `<0x40` literal n px, `0x40-0x7f` run, `>=0x80` skip (transparent) `n&0x3f`.
Pixels are RGB565 (2 bytes, when X is large) or BGR (3 bytes). zlib-wrapped files are `[clen,rlen,zlib]`.

Unsupported: `fx/Map` (1019), `fx/MapScriptTemplate` (407) and `*ObjectTable`/`Attr` files: XOR-encrypted with a global position keystream not yet recovered.
Details per file: `AssetsDecoded/_report.json`.
