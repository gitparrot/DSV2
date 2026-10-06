"""Blender script: build a Dead Space 2 character from a StrUnpack'ed stream and export FBX.

    blender -b --factory-startup -P pipeline/ds2_to_fbx.py -- <unpacked dir> <out.fbx> [--skeleton zombieb] [--caps]
        [--skip <regex>]   (leave pieces out, e.g. the Divider's tongue, modelled 5 m long and straight)
        [--attach <other skeleton>:<joint>]   (also take meshes bound to another skeleton in the stream, rigidly
                                                on one joint: Isaac's helmet has its own skeleton -> m_neck2 = head)
        [--keep-bones <regex>]   (only triangles mainly weighted to matching joints, e.g. first-person arms)
        [--scale <factor>]   (uniform; Isaac is stored at ~55% size, use 1.8)
        [--rcb-from <other unpacked dir>]   (skeleton from another stream: Isaac's suits use global_assets' "player")
        [--names-from <other unpacked dir>]   (joint names from another stream's .hkx with the same skeleton;
                                               the Enhanced Slasher's own .hkx has no Deform_ names for it)

Skeleton: .rcb inverse bind matrices + hierarchy; joint names from the .hkx.win (matched by hash).
Meshes: every skinned *_dism.geo piece (wound caps *_pc/*_sc only with --caps; lodmodel skipped).
Textures: <dir>/dds/*.dds from pipeline/ds2_tg4.py (<model>_c base colour, _n DXT5_NM normal, _sp specular).
Dead Space is Y-up; the scene is built Z-up and the FBX is written Y-up like any Blender export.
Output stays in git-ignored ds2_export/ (also saves a .blend next to it).
"""
import difflib, json, os, re, struct, sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ds2_geo  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
src, out_fbx = os.path.abspath(argv[0]), os.path.abspath(argv[1])
skel_name = argv[argv.index("--skeleton") + 1] if "--skeleton" in argv else None
with_caps = "--caps" in argv
names_from = [os.path.abspath(argv[i + 1]) for i, a in enumerate(argv) if a == "--names-from"]
skip = [argv[i + 1] for i, a in enumerate(argv) if a == "--skip"]  # regexes of mesh pieces to leave out
attach = dict(argv[i + 1].split(":", 1) for i, a in enumerate(argv) if a == "--attach")  # skeleton -> joint
# Isaac is stored at ~55% of his size (1.03 m); --scale 1.8 gives him his real ~1.85 m and shoulder width
size = float(argv[argv.index("--scale") + 1]) if "--scale" in argv else 1.0
# keep only triangles mainly weighted to joints matching this regex (Isaac's first-person arms: his upper arms are
# part of the merged chest mesh, and the chest must not sit in front of the camera)
keep_bones = re.compile(argv[argv.index("--keep-bones") + 1], re.I) if "--keep-bones" in argv else None
model = os.path.basename(os.path.normpath(src))

Y_UP_TO_Z_UP = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))

bpy.ops.wm.read_factory_settings(use_empty=True)

# ---- skeleton --------------------------------------------------------------------------------------
rcb_dirs = [src] + [os.path.abspath(argv[i + 1]) for i, a in enumerate(argv) if a == "--rcb-from"]
skels = {}
for d in rcb_dirs:  # Isaac's suits use the shared "player" skeleton from global_assets
    rcb_dir = os.path.join(d, "RCB")
    for f in sorted(os.listdir(rcb_dir)) if os.path.isdir(rcb_dir) else []:
        for s_ in ds2_geo.read_rcb(open(os.path.join(rcb_dir, f), "rb").read())["skeletons"]:
            skels.setdefault(s_["name"], s_)
skel = skels[skel_name] if skel_name else list(skels.values())[-1]
geos = ds2_geo.load_stream_geos(src)

# only meshes bound to this skeleton: other skeletons in the stream reuse the same joint numbers
sizes = sorted(len(s_["parents"]) for s_ in skels.values())


def owner(g):
    """A mesh belongs to the smallest skeleton that can hold its highest joint index (the Divider's split-off
    creatures have their own small skeletons; Isaac's suit lists 131 of the player skeleton's 132 joints)."""
    if not g["bones"]:
        return len(skel["parents"])
    need = max(b["rcb_index"] for b in g["bones"]) + 1
    return min((n for n in sizes if n >= need), default=None)


attach_sizes = {len(skels[k]["parents"]): v for k, v in attach.items()}


def bound_here(g):
    return owner(g) == len(skel["parents"])


attached = {k: g for k, g in geos.items() if not bound_here(g) and owner(g) in attach_sizes}
geos = {k: g for k, g in geos.items() if bound_here(g)}
hashes = {b["rcb_index"]: b["hash"] for g in geos.values() for b in g["bones"]}
hkx = b"".join(open(os.path.join(d, "HKX", f), "rb").read()
               for d in [src, *names_from] if os.path.isdir(os.path.join(d, "HKX")) for f in os.listdir(os.path.join(d, "HKX")))
known = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ds2_bone_names.txt")
hkx += b" " + b" ".join(l.strip().encode() for l in open(known, encoding="utf-8") if l.strip() and not l.startswith("#"))
by_hash = ds2_geo.hkx_bone_names(hkx, set(hashes.values()))
names = [by_hash.get(hashes.get(i), f"bone_{i:02d}") for i in range(len(skel["parents"]))]
print(f"[ds2] skeleton {skel['name']}: {len(names)} bones, {sum(1 for n in names if not n.startswith('bone_'))} named")

arm_data = bpy.data.armatures.new(f"{model}_rig")
arm = bpy.data.objects.new(f"{model}_rig", arm_data)
bpy.context.scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
world = []
for i, inv in enumerate(skel["inv_bind"]):
    m = Matrix(inv).transposed().inverted()  # stored row-major (System.Numerics) inverse bind
    m = Y_UP_TO_Z_UP @ m
    m.translation = m.translation * size
    world.append(m)
ebones = []
for i, n in enumerate(names):
    eb = arm_data.edit_bones.new(n)
    eb.head, eb.tail = (0, 0, 0), (0, 0.05, 0)
    eb.matrix = world[i]
    ebones.append(eb)
for i, p in enumerate(skel["parents"]):
    if p >= 0:
        ebones[i].parent = ebones[p]
for i, eb in enumerate(ebones):  # point each bone at its only child where there is one, for readable rigs
    kids = [j for j, p in enumerate(skel["parents"]) if p == i]
    if len(kids) == 1 and (ebones[kids[0]].head - eb.head).length > 1e-3:
        eb.tail = ebones[kids[0]].head
bpy.ops.object.mode_set(mode="OBJECT")

# ---- materials -------------------------------------------------------------------------------------
# One Blender material per Dead Space texture set (<prefix>_c/_ca, _n, _sp/_s). Single-set models use
# <model>_*; multi-set models (Isaac's suit) map each mesh's material hash to its set: the hash is the u32 at
# offset 8 of a Material/*.Material|.mtlb file, whose name ends in the set ("..._mat_skinned_playerminerupperbo").
dds = os.path.join(src, "dds")
fmt_path = os.path.join(dds, "formats.json")
formats = json.load(open(fmt_path)) if os.path.exists(fmt_path) else {}
SUFFIXES = ("_ca", "_c", "_n", "_sp", "_sc", "_s", "_o")
sets = sorted({k[: -len(sfx)] for k in formats for sfx in SUFFIXES if k.endswith(sfx)})
set_of_hash = {}
mat_dir = os.path.join(src, "Material")
for f in sorted(os.listdir(mat_dir)) if os.path.isdir(mat_dir) else []:
    data = open(os.path.join(mat_dir, f), "rb").read()
    if len(data) < 12:
        continue
    stem = re.sub(r"^\d+_", "", f).rsplit(".", 1)[0].split("_mat_")[-1].replace("skinned_", "")
    best = max(sets, key=lambda t: (len(os.path.commonprefix([t, stem])), -abs(len(t) - len(stem))), default=None)
    if best and len(os.path.commonprefix([best, stem])) >= min(8, len(stem)):
        set_of_hash[struct.unpack_from("<I", data, 8)[0]] = best
materials = {}


def material_for(prefix):
    if prefix in materials:
        return materials[prefix]
    mat = bpy.data.materials.new(prefix)
    if not mat.node_tree:
        mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")

    def tex(suffix, colorspace):
        p = os.path.join(dds, f"{prefix}_{suffix}.dds")
        if not os.path.exists(p):  # misspelt sets exist: Isaac's helmet colour map is "playermnerhelmet_c"
            close = difflib.get_close_matches(f"{prefix}_{suffix}", [k for k in formats if k.endswith(f"_{suffix}")], 1, 0.9)
            if not close:
                return None
            p = os.path.join(dds, f"{close[0]}.dds")
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = bpy.data.images.load(p)
        node.image.colorspace_settings.name = colorspace
        return node

    c = tex("c", "sRGB") or tex("ca", "sRGB")  # base colour is _ca (colour + alpha) on the Divider
    if c:
        nt.links.new(c.outputs["Color"], bsdf.inputs["Base Color"])
    n = tex("n", "Non-Color")
    if n and not formats.get(f"{prefix}_n", "DXT5_NM").endswith("_NM"):  # plain RGB normal map
        nmap = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(n.outputs["Color"], nmap.inputs["Color"])
        nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    elif n:  # DXT5_NM: X in alpha, Y in green, Z rebuilt
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        comb = nt.nodes.new("ShaderNodeCombineColor")
        nt.links.new(n.outputs["Color"], sep.inputs["Color"])
        nt.links.new(n.outputs["Alpha"], comb.inputs["Red"])
        nt.links.new(sep.outputs["Green"], comb.inputs["Green"])
        comb.inputs["Blue"].default_value = 1.0
        nmap = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(comb.outputs["Color"], nmap.inputs["Color"])
        nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    sp = tex("sp", "Non-Color") or tex("s", "Non-Color") or tex("sc", "Non-Color")  # _sp Slashers, _s Pack
    if sp:
        nt.links.new(sp.outputs["Color"], bsdf.inputs["Specular IOR Level"])
    materials[prefix] = mat
    return mat


# ---- meshes ----------------------------------------------------------------------------------------
pieces = 0
for key, g in list(geos.items()) + list(attached.items()):
    rigid_on = attach_sizes.get(owner(g)) if key in attached else None
    if any(re.search(rx, key, re.I) for rx in skip):
        continue
    if not with_caps and re.search(r"_(pc|sc)_dism|_cap_", key):  # wound caps (Slasher _pc/_sc, Pack *_cap_*)
        continue
    for m in g["meshes"]:
        name = m["name"].replace("Shape", "")
        me = bpy.data.meshes.new(name)
        verts = [(Y_UP_TO_Z_UP @ Vector(v["pos"])) * size for v in m["verts"]]
        if rigid_on:  # modelled around its own skeleton's origin, which the game puts on that joint
            offset = world[names.index(rigid_on)].to_translation()
            verts = [v + offset for v in verts]
        faces = m["faces"]
        if keep_bones:
            kept = [bool(v["influences"]) and bool(keep_bones.search(names[max(v["influences"], key=lambda iw: iw[1])[0]]))
                    for v in m["verts"]]
            faces = [f for f in faces if all(kept[i] for i in f)]
            if not faces:
                continue
        me.from_pydata([tuple(v) for v in verts], [], faces)
        uv = me.uv_layers.new(name="UVMap")
        for poly in me.polygons:
            for li in poly.loop_indices:
                u, v = m["verts"][me.loops[li].vertex_index]["uv"]
                uv.data[li].uv = (u, 1.0 - v)
        me.normals_split_custom_set_from_vertices(
            [tuple((Y_UP_TO_Z_UP.to_3x3() @ Vector(v["normal"])).normalized()) for v in m["verts"]])
        me.materials.append(material_for(set_of_hash.get(m["mtlb"], model)))
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        groups = {}
        for vi, v in enumerate(m["verts"]):
            for bi, w in ([(names.index(rigid_on), 1.0)] if rigid_on else v["influences"]):
                vg = groups.get(bi) or ob.vertex_groups.new(name=names[bi])
                groups[bi] = vg
                vg.add([vi], w, "REPLACE")
        ob.parent = arm
        mod = ob.modifiers.new("Armature", "ARMATURE")
        mod.object = arm
        pieces += 1
print(f"[ds2] {pieces} mesh pieces")

os.makedirs(os.path.dirname(os.path.abspath(out_fbx)), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.splitext(out_fbx)[0] + ".blend")
bpy.ops.export_scene.fbx(filepath=out_fbx, add_leaf_bones=False, path_mode="COPY", embed_textures=True,
                         mesh_smooth_type="FACE", use_armature_deform_only=False)
print(f"[ds2] wrote {out_fbx}")
