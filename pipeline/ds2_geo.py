"""Readers for Dead Space 2 (PC) .geo meshes and .rcb skeletons, as unpacked by Gibbed.Visceral.StrUnpack.

Ported from MeltyTool (github.com/MeltyPlayer/MeltyTool, GPL-3.0): VisceralGames/src/schema/geo/Geo.cs,
schema/rcb/Rcb.cs and api/PackedVectorUtil.cs. This file is therefore GPL-3.0 as well.
DS2 difference found on the PC (2026-10-05): StrUnpack splits each .geo into Mesh/NNNN_x.geo and
MeshVolatile/NNNN+1_x.geo; the header's length field equals their combined size, so join them.

Pure Python (no Blender needed). `python pipeline/ds2_geo.py <unpacked stream dir>` prints a summary.
"""
import os, re, struct, sys


class R:
    def __init__(self, data):
        self.d, self.p = data, 0

    def u32(self):
        v, = struct.unpack_from("<I", self.d, self.p); self.p += 4; return v

    def i32(self):
        v, = struct.unpack_from("<i", self.d, self.p); self.p += 4; return v

    def u16(self):
        v, = struct.unpack_from("<H", self.d, self.p); self.p += 2; return v

    def f32s(self, n):
        v = struct.unpack_from(f"<{n}f", self.d, self.p); self.p += 4 * n; return v

    def cstr_at(self, off):
        end = self.d.index(b"\0", off)
        return self.d[off:end].decode("ascii", "replace")

    def mat_at(self, off):  # 4x4 row-major as stored (System.Numerics layout)
        v = struct.unpack_from("<16f", self.d, off)
        return [list(v[0:4]), list(v[4:8]), list(v[8:12]), list(v[12:16])]


def _signed10(x):
    return x - 1024 if x & 0x200 else x


def packed_normal(v):
    return tuple(_signed10((v >> (10 * i)) & 0x3FF) / 512.0 for i in range(3))


def name_hash(s):
    """Visceral name hash (Gibbed StringHelpers.HashName): lowercase, h = h * 65599 + c."""
    h = 0
    for c in s.lower():
        h = (h * 65599 + ord(c)) & 0xFFFFFFFF
    return h


def read_geo(data):
    """DS2 PC layout (worked out on the Slasher, differs from MeltyTool's DS3 Geo.cs):
    header 0x34 mesh count, 0x38 bone count, 0x50 mesh table (0x100 per mesh), 0x60 bone records
    (name hash, rcb index), 0x68 vertex/uv/index buffer records (size, count, flags|stride, offset).
    Mesh entry: +0x04 flags (0xF0000 = influences per vertex, 0 = rigid), +0x0C material hash, +0x30 index count,
    +0x38 vertex count, +0x40 base vertex (u16), +0x44 bone palette (u8 pairs: rcb index, geo bone),
    +0x84 vertex offset, +0x88 index offset. Skinned vertex 32 B: pos 3f, normal u32, tangent u32,
    4 palette slots u8, 4 weights u16. Rigid vertex 20 B (no skin; whole mesh on palette[0]).
    UVs: the stride-8 buffer record, 2 floats per vertex."""
    if data[:4] != b"MGAE":
        raise ValueError("not an MGAE geo")
    u32 = lambda o: struct.unpack_from("<I", data, o)[0]
    if u32(12) != len(data):
        raise ValueError(f"geo length {len(data)} != header {u32(12)} (join Mesh + MeshVolatile)")
    cstr = lambda o: data[o:data.index(bytes(1), o)].decode("ascii", "replace")
    mesh_count, bone_count = u32(0x34), u32(0x38)
    buf_count = sum(struct.unpack_from("<HH", data, 0x3C))
    table_off, bone_data_off, buf_off = u32(0x50), u32(0x60), u32(0x68)
    bufs = [struct.unpack_from("<4I", data, buf_off + 16 * i) for i in range(buf_count)]
    uv_buf = next((b for b in bufs if b[2] & 0xFF == 8), None)
    bones = [dict(zip(("hash", "rcb_index"), struct.unpack_from("<II", data, bone_data_off + 8 * i)))
             for i in range(bone_count)]

    meshes = []
    for m in range(mesh_count):
        e = table_off + 0x100 * m
        flags, mtlb = u32(e + 4), u32(e + 0x0C)
        skinned = bool(flags & 0xF0000)  # influences per vertex (0 = rigid)
        icount, vcount = u32(e + 0x30), u32(e + 0x38)
        base = struct.unpack_from("<H", data, e + 0x40)[0]
        pal_off, v_off, i_off = u32(e + 0x44), u32(e + 0x84), u32(e + 0x88)
        palette = list(data[pal_off:pal_off + 2 * 256:2]) if pal_off else []
        stride = 32 if skinned else 20
        verts = []
        for k in range(vcount):
            o = v_off + stride * (base + k)
            pos = struct.unpack_from("<3f", data, o)
            n, t = struct.unpack_from("<II", data, o + 12)
            if skinned:
                slots = data[o + 20:o + 24]
                w = struct.unpack_from("<4H", data, o + 24)
                infl = [(palette[s], x / 65535.0) for s, x in zip(slots, w) if x]
            else:
                infl = [(palette[0], 1.0)] if palette else []
            uv = struct.unpack_from("<2f", data, uv_buf[3] + 8 * (base + k)) if uv_buf else (0.0, 0.0)
            verts.append({"pos": pos, "normal": packed_normal(n), "uv": uv, "influences": infl})
        idx = struct.unpack_from(f"<{icount}H", data, i_off)
        faces = [(idx[f] - base, idx[f + 1] - base, idx[f + 2] - base) for f in range(0, icount - 2, 3)]
        meshes.append({"name": cstr(u32(e)), "mtlb": mtlb, "skinned": skinned, "verts": verts, "faces": faces})
    return {"name": cstr(u32(0x20)), "bones": bones, "meshes": meshes}


def hkx_bone_names(hkx_data, hashes):
    """Map Visceral name hashes to the joint names stored as plain strings in a Havok .hkx.win."""
    words = {m.group().decode() for m in re.finditer(rb"[A-Za-z_][A-Za-z0-9_]{2,}", hkx_data)}
    table = {name_hash(w): w for w in words}
    return {h: table[h] for h in hashes if h in table}


def read_rcb(data):
    r = R(data)
    r.u32(); r.p += 4
    main_bnk = r.u32(); r.p += 12
    count, data_off = r.u32(), r.u32()
    skels = []
    for s in range(count):
        r.p = data_off + 24 * s
        bnk, name = r.u32(), r.cstr_at(r.u32())
        n, parent_off, bone_start = r.u32(), r.u32(), r.u32()
        parents = [struct.unpack_from("<i", data, parent_off + 16 * i)[0] for i in range(n)]
        inv_binds = [r.mat_at(bone_start + 64 * i) for i in range(n)]
        skels.append({"bnk": bnk, "name": name, "parents": parents, "inv_bind": inv_binds})
    return {"main_bnk": main_bnk, "skeletons": skels}


def load_stream_geos(unpacked_dir):
    """Join Mesh/NNNN_x.geo with MeshVolatile/MMMM_x.geo (same x) and parse each."""
    mesh_dir, vol_dir = os.path.join(unpacked_dir, "Mesh"), os.path.join(unpacked_dir, "MeshVolatile")
    vol = {}
    if os.path.isdir(vol_dir):
        for f in os.listdir(vol_dir):
            vol[re.sub(r"^\d+_", "", f)] = os.path.join(vol_dir, f)
    out = {}
    for f in sorted(os.listdir(mesh_dir)):
        key = re.sub(r"^\d+_", "", f)
        data = open(os.path.join(mesh_dir, f), "rb").read()
        if key in vol:
            data += open(vol[key], "rb").read()
        if struct.unpack_from("<I", data, 0x38)[0] == 0:
            continue  # lodmodel.geo: unskinned far LOD with another vertex layout, not needed
        out[key] = read_geo(data)
    return out


def load_stream_rcb(unpacked_dir):
    d = os.path.join(unpacked_dir, "RCB")
    files = sorted(os.listdir(d)) if os.path.isdir(d) else []
    return read_rcb(open(os.path.join(d, files[0]), "rb").read()) if files else None


if __name__ == "__main__":
    src = sys.argv[1]
    rcb = load_stream_rcb(src)
    if rcb:
        for s in rcb["skeletons"]:
            print(f"rcb skeleton {s['name']!r}: {len(s['parents'])} bones")
    for key, g in load_stream_geos(src).items():
        for m in g["meshes"]:
            bad = sum(1 for f in m["faces"] for i in f if not 0 <= i < len(m["verts"]))
            print(f"{key}: {m['name']} skinned={m['skinned']} verts={len(m['verts'])} tris={len(m['faces'])} bad_idx={bad}")
