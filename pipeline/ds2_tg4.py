"""Turn Dead Space 2 .tg4h/.tg4d texture pairs (from Gibbed StrUnpack) into .dds files Blender can open.

Worked out on the Slasher (2026-10-05): .tg4h holds width/height (u16 at 0x20/0x22), mip count (u8 at 0x26)
and a format tag such as "DXT1c", "DXT5", "DXT5_NM"; .tg4d is the raw DXT mip chain. DXT5_NM is a DXT5
normal map with X in alpha and Y in green (swizzled; the Blender script rebuilds it).
Gibbed.Visceral.ConvertTG4 is only a hard-coded test stub, hence this file.

    python pipeline/ds2_tg4.py <unpacked stream dir> <out dir> [--png]

--png also writes the top mip as RGBA .png (the Vermintide 2 SDK only accepts uncompressed texture sources;
for DXT5_NM the PNG keeps X in alpha and Y in green).
"""
import os, re, struct, sys

FOURCC = {"DXT1": b"DXT1", "DXT3": b"DXT3", "DXT5": b"DXT5"}


def read_tg4h(data):
    width, height = struct.unpack_from("<HH", data, 0x20)
    mips = data[0x26]
    m = re.search(rb"(DXT[135][A-Za-z_]*)\0", data)
    if not m:
        raise ValueError("no DXT format tag in tg4h")
    return width, height, mips, m.group(1).decode()


def mip_chain_size(w, h, mips, block):
    total = 0
    for _ in range(mips):
        total += max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * block
        w, h = max(1, w // 2), max(1, h // 2)
    return total


def to_dds(tg4h, tg4d):
    w, h, mips, fmt = read_tg4h(tg4h)
    fourcc = FOURCC[fmt[:4]]
    block = 8 if fourcc == b"DXT1" else 16
    need = mip_chain_size(w, h, mips, block)
    if len(tg4d) < need:
        raise ValueError(f"tg4d {len(tg4d)} bytes < {need} for {w}x{h} {fmt} x{mips}")
    flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x20000 | 0x80000  # caps|height|width|pixelformat|mipcount|linearsize
    header = struct.pack("<4sIIIIIII44x", b"DDS ", 124, flags, h, w, max(1, w // 4) * max(1, h // 4) * block, 0, mips)
    pixfmt = struct.pack("<II4s5I", 32, 0x4, fourcc, 0, 0, 0, 0, 0)
    caps = struct.pack("<5I", 0x1000 | 0x400000 | 0x8, 0, 0, 0, 0)
    return header + pixfmt + caps + tg4d[:need], fmt


def _565(c):
    return ((c >> 11) & 31) * 255 // 31, ((c >> 5) & 63) * 255 // 63, (c & 31) * 255 // 31


def _color_block(b, rgba, x0, y0, w, opaque):
    c0, c1, bits = struct.unpack_from("<HHI", b)
    p0, p1 = _565(c0), _565(c1)
    if c0 > c1 or opaque:
        pal = [p0 + (255,), p1 + (255,), tuple((2 * a + c) // 3 for a, c in zip(p0, p1)) + (255,),
               tuple((a + 2 * c) // 3 for a, c in zip(p0, p1)) + (255,)]
    else:
        pal = [p0 + (255,), p1 + (255,), tuple((a + c) // 2 for a, c in zip(p0, p1)) + (255,), (0, 0, 0, 0)]
    for i in range(16):
        o = ((y0 + i // 4) * w + x0 + i % 4) * 4
        rgba[o:o + 4] = bytes(pal[(bits >> (2 * i)) & 3])


def _alpha_block(b, rgba, x0, y0, w):
    a0, a1 = b[0], b[1]
    bits = int.from_bytes(b[2:8], "little")
    if a0 > a1:
        pal = [a0, a1] + [((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)]
    else:
        pal = [a0, a1] + [((5 - i) * a0 + i * a1) // 5 for i in range(1, 5)] + [0, 255]
    for i in range(16):
        rgba[((y0 + i // 4) * w + x0 + i % 4) * 4 + 3] = pal[(bits >> (3 * i)) & 7]


def decode_top_mip(tg4h, tg4d):
    """Top mip of a .tg4 pair as RGBA bytes (the SDK only takes uncompressed sources)."""
    w, h, _, fmt = read_tg4h(tg4h)
    dxt1 = fmt.startswith("DXT1")
    block = 8 if dxt1 else 16
    rgba = bytearray(w * h * 4)
    k = 0
    for by in range(0, h, 4):
        for bx in range(0, w, 4):
            blk = tg4d[k:k + block]
            if dxt1:
                _color_block(blk, rgba, bx, by, w, opaque=False)
            else:
                _color_block(blk[8:], rgba, bx, by, w, opaque=True)
                _alpha_block(blk, rgba, bx, by, w)
            k += block
    return w, h, rgba


def write_png(path, w, h, rgba):
    import zlib
    raw = b"".join(b"\0" + bytes(rgba[y * w * 4:(y + 1) * w * 4]) for y in range(h))
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def convert_dir(unpacked_dir, out_dir, png=False):
    hdir, ddir = os.path.join(unpacked_dir, "tg4h"), os.path.join(unpacked_dir, "tg4d")
    datas = {re.sub(r"^\d+_", "", f).rsplit(".", 1)[0]: os.path.join(ddir, f) for f in os.listdir(ddir)}
    os.makedirs(out_dir, exist_ok=True)
    done = {}
    for f in sorted(os.listdir(hdir)):
        name = re.sub(r"^\d+_", "", f).rsplit(".", 1)[0]
        if name not in datas:
            continue
        try:
            dds, fmt = to_dds(open(os.path.join(hdir, f), "rb").read(), open(datas[name], "rb").read())
        except (ValueError, KeyError) as e:
            print(f"skip {name}: {e}")
            continue
        path = os.path.join(out_dir, name + ".dds")
        open(path, "wb").write(dds)
        if png:
            w, h, rgba = decode_top_mip(open(os.path.join(hdir, f), "rb").read(), open(datas[name], "rb").read())
            write_png(os.path.join(out_dir, name + ".png"), w, h, rgba)
        done[name] = (path, fmt)
        print(f"{path} ({fmt}){' + .png' if png else ''}")
    import json
    with open(os.path.join(out_dir, "formats.json"), "w", encoding="utf-8") as f:
        json.dump({k: v[1] for k, v in done.items()}, f, indent=1)  # read by make_sdk_unit.py / ds2_to_fbx.py
    return done


if __name__ == "__main__":
    convert_dir(sys.argv[1], sys.argv[2], png="--png" in sys.argv)
