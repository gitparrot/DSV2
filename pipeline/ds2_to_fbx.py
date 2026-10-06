"""Blender script: build a Dead Space 2 character from a StrUnpack'ed stream and export FBX.

    blender -b --factory-startup -P pipeline/ds2_to_fbx.py -- <unpacked dir> <out.fbx> [--skeleton zombieb] [--caps]
        [--skip <regex>]   (leave pieces out, e.g. the Divider's tongue, modelled 5 m long and straight)
        [--names-from <other unpacked dir>]   (joint names from another stream's .hkx with the same skeleton;
                                               the Enhanced Slasher's own .hkx has no Deform_ names for it)

Skeleton: .rcb inverse bind matrices + hierarchy; joint names from the .hkx.win (matched by hash).
Meshes: every skinned *_dism.geo piece (wound caps *_pc/*_sc only with --caps; lodmodel skipped).
Textures: <dir>/dds/*.dds from pipeline/ds2_tg4.py (<model>_c base colour, _n DXT5_NM normal, _sp specular).
Dead Space is Y-up; the scene is built Z-up and the FBX is written Y-up like any Blender export.
Output stays in git-ignored ds2_export/ (also saves a .blend next to it).
"""
import json, os, re, sys

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
model = os.path.basename(os.path.normpath(src))

Y_UP_TO_Z_UP = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))

bpy.ops.wm.read_factory_settings(use_empty=True)

# ---- skeleton --------------------------------------------------------------------------------------
rcb = ds2_geo.load_stream_rcb(src)
skels = {s["name"]: s for s in rcb["skeletons"]}
skel = skels[skel_name] if skel_name else rcb["skeletons"][-1]
geos = ds2_geo.load_stream_geos(src)

# only meshes bound to this skeleton: other skeletons in the stream reuse the same joint numbers
geos = {k: g for k, g in geos.items() if not g["bones"] or len(g["bones"]) == len(skel["parents"])}
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
    world.append(Y_UP_TO_Z_UP @ m)
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

# ---- material --------------------------------------------------------------------------------------
dds = os.path.join(src, "dds")
mat = bpy.data.materials.new(model)
nt = mat.node_tree if mat.node_tree else None
if nt is None:
    mat.use_nodes = True
    nt = mat.node_tree
bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")


def tex(suffix, colorspace):
    p = os.path.join(dds, f"{model}_{suffix}.dds")
    if not os.path.exists(p):
        return None
    node = nt.nodes.new("ShaderNodeTexImage")
    node.image = bpy.data.images.load(p)
    node.image.colorspace_settings.name = colorspace
    return node


c = tex("c", "sRGB") or tex("ca", "sRGB")  # base colour is _ca (colour + alpha) on the Divider
if c:
    nt.links.new(c.outputs["Color"], bsdf.inputs["Base Color"])
n = tex("n", "Non-Color")
fmt_path = os.path.join(dds, "formats.json")
n_fmt = json.load(open(fmt_path)).get(f"{model}_n", "DXT5_NM") if os.path.exists(fmt_path) else "DXT5_NM"
if n and not n_fmt.endswith("_NM"):  # plain RGB normal map
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
sp = tex("sp", "Non-Color") or tex("s", "Non-Color")  # specular is _sp on Slashers, _s on the Pack
if sp:
    nt.links.new(sp.outputs["Color"], bsdf.inputs["Specular IOR Level"])

# ---- meshes ----------------------------------------------------------------------------------------
pieces = 0
for key, g in geos.items():
    if g["bones"] and len(g["bones"]) != len(skel["parents"]):
        continue  # bound to another skeleton in the stream (the Divider's head/hands/feet as separate creatures)
    if any(re.search(rx, key, re.I) for rx in skip):
        continue
    if not with_caps and re.search(r"_(pc|sc)_dism|_cap_", key):  # wound caps (Slasher _pc/_sc, Pack *_cap_*)
        continue
    for m in g["meshes"]:
        name = m["name"].replace("Shape", "")
        me = bpy.data.meshes.new(name)
        verts = [(Y_UP_TO_Z_UP @ Vector(v["pos"])) for v in m["verts"]]
        me.from_pydata([tuple(v) for v in verts], [], m["faces"])
        uv = me.uv_layers.new(name="UVMap")
        for poly in me.polygons:
            for li in poly.loop_indices:
                u, v = m["verts"][me.loops[li].vertex_index]["uv"]
                uv.data[li].uv = (u, 1.0 - v)
        me.normals_split_custom_set_from_vertices(
            [tuple((Y_UP_TO_Z_UP.to_3x3() @ Vector(v["normal"])).normalized()) for v in m["verts"]])
        me.materials.append(mat)
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        groups = {}
        for vi, v in enumerate(m["verts"]):
            for bi, w in v["influences"]:
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
