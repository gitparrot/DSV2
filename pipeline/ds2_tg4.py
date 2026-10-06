"""Turn Dead Space 2 .tg4h/.tg4d texture pairs (from Gibbed StrUnpack) into .dds files Blender can open.

Worked out on the Slasher (2026-10-05): .tg4h holds width/height (u16 at 0x20/0x22), mip count (u8 at 0x26)
and a format tag such as "DXT1c", "DXT5", "DXT5_NM"; .tg4d is the raw DXT mip chain. DXT5_NM is a DXT5
normal map with X in alpha and Y in green (swizzled; the Blender script rebuilds it).
Gibbed.Visceral.ConvertTG4 is only a hard-coded test stub, hence this file.

    python pipeline/ds2_tg4.py <unpacked stream dir> <out dir>
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


def convert_dir(unpacked_dir, out_dir):
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
        done[name] = (path, fmt)
        print(f"{path} ({fmt})")
    return done


if __name__ == "__main__":
    convert_dir(sys.argv[1], sys.argv[2])
