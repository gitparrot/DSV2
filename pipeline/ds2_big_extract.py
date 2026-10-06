"""Copy entries out of Dead Space 2's BIGH archives (DS2DAT*.DAT), read-only on the game folder.

Same layout Gibbed.Visceral's BigFile.cs reads: 'BIGH', total size (LE), count and header size (BE),
then count x (offset, size, name hash) big-endian. Entries are stored raw, so a byte copy matches
what BigViewer saves. Output goes to extracted/ (git-ignored); never commit it.

    python pipeline/ds2_big_extract.py <DS2 folder> DS2DAT6.DAT 0x258D62B5 [more hashes] [-o extracted/ds2]
"""
import argparse, os, struct


def entries(path):
    with open(path, "rb") as f:
        magic, = struct.unpack(">I", f.read(4))
        if magic != 0x42494748:
            raise ValueError(f"{path}: not a BIGH archive")
        f.read(4)
        count, _ = struct.unpack(">II", f.read(8))
        raw = f.read(count * 12)
    return [struct.unpack(">III", raw[i * 12:i * 12 + 12]) for i in range(count)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ds2_dir")
    ap.add_argument("archive")
    ap.add_argument("hashes", nargs="+")
    ap.add_argument("-o", "--out", default="extracted/ds2")
    a = ap.parse_args()
    path = os.path.join(a.ds2_dir, a.archive)
    want = {int(h, 16) for h in a.hashes}
    os.makedirs(a.out, exist_ok=True)
    with open(path, "rb") as f:
        for off, size, name in entries(path):
            if name not in want:
                continue
            f.seek(off)
            dst = os.path.join(a.out, f"{os.path.splitext(a.archive)[0]}_{name:08X}.str")
            with open(dst, "wb") as o:
                o.write(f.read(size))
            want.discard(name)
            print(f"{dst} ({size} bytes)")
    for h in want:
        print(f"not found: 0x{h:08X}")


if __name__ == "__main__":
    main()
