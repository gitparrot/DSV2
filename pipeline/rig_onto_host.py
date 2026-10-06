"""Blender script (step 5): rig a Dead Space 2 model onto a Vermintide 2 enemy's own skeleton and export FBX.

    blender -b -P pipeline/rig_onto_host.py -- --source ds2_export/slasher.blend
        --host extracted/vt2/chaos_fanatic_nofix.blend --map pipeline/bone_maps/slasher_to_vt2_human.json
        --bones pipeline/bones/chaos_fanatic.txt --out ds2_export/slasher_fanatic.fbx

Why the host skeleton is used as-is: the mod pins every skin bone to the host bone of the same name
(World.link_unit), so the skin's rest pose must be the host's rest pose. The host .blend must be imported
by Bitsquid Blender Tools WITHOUT "Fix bone rotation" (that changes rest orientations).

What it does: turn the source model to face the host's way; point/stretch the source bones onto the host
joints (map "head", "stretch", "aim"); bake that pose into the mesh; move each source bone's weights to its
mapped host joint; bind the meshes to the host armature (renamed "Armature" so the FBX has no extra root).
Writes <out>.fbx and <out>.blend (git-ignored), plus the host's own meshes hidden in "host_ref" for comparison.
"""
import json, math, os, sys

import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
arg = lambda k: os.path.abspath(argv[argv.index(k) + 1])
source, host, map_path, bones_path, out_fbx = (arg(k) for k in ("--source", "--host", "--map", "--bones", "--out"))
cfg = json.load(open(map_path, encoding="utf-8"))
bmap = cfg["bones"]
linked = [ln.strip() for ln in open(bones_path, encoding="utf-8") if ln.strip() and not ln.startswith("#")]

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def append_objects(path):
    with bpy.data.libraries.load(path) as (src, dst):
        dst.objects = list(src.objects)
    return [o for o in dst.objects if o is not None]


# ---- load ------------------------------------------------------------------------------------------
src_objs = append_objects(source)
for o in src_objs:
    scene.collection.objects.link(o)
src_arm = next(o for o in src_objs if o.type == "ARMATURE")
src_meshes = [o for o in src_objs if o.type == "MESH"]

host_objs = append_objects(host)
ref = bpy.data.collections.new("host_ref")
scene.collection.children.link(ref)
for o in host_objs:
    (scene.collection if o.type == "ARMATURE" else ref).objects.link(o)
host_arm = max((o for o in host_objs if o.type == "ARMATURE"), key=lambda a: len(a.data.bones))
if host_arm.matrix_world != Matrix.Identity(4):
    sys.exit("[rig] host armature has an object transform; expected identity")

missing = [b.name for b in src_arm.data.bones if b.name not in bmap]
bad = sorted({r["weights"] for r in bmap.values() if r["weights"] not in linked})
if missing or bad:
    sys.exit(f"[rig] map incomplete: no row for {missing}; weight targets not linked: {bad}")


def host_point(spec):
    hb = host_arm.data.bones
    if isinstance(spec, str):
        return host_arm.matrix_world @ hb[spec].head_local
    a, b, t = spec
    return (host_arm.matrix_world @ hb[a].head_local).lerp(host_arm.matrix_world @ hb[b].head_local, t)


# ---- face the host's way ---------------------------------------------------------------------------
src_arm.matrix_world = Matrix.Rotation(math.radians(cfg.get("rotate_z_degrees", 0)), 4, "Z") @ src_arm.matrix_world
bpy.context.view_layer.update()

# ---- edit source bones: limb directions and scale inheritance --------------------------------------
bpy.context.view_layer.objects.active = src_arm
bpy.ops.object.mode_set(mode="EDIT")
eb = src_arm.data.edit_bones
for name, row in bmap.items():
    b = eb.get(name)
    if b is None:
        continue
    if "tail_to" in row:
        b.tail = eb[row["tail_to"]].head
    fitted = any(k in row for k in ("head", "stretch", "aim"))
    b.inherit_scale = "NONE" if fitted or row.get("rigid") else "FULL"
bpy.ops.object.mode_set(mode="OBJECT")

# ---- fit with constraints --------------------------------------------------------------------------
targets = bpy.data.collections.new("fit_targets")
scene.collection.children.link(targets)


def empty_at(p, name):
    e = bpy.data.objects.new(name, None)
    e.location = p
    targets.objects.link(e)
    return e


for name, row in bmap.items():
    pb = src_arm.pose.bones.get(name)
    if pb is None:
        continue
    if "head" in row:
        c = pb.constraints.new("COPY_LOCATION")
        c.target = empty_at(host_point(row["head"]), f"head_{name}")
    if "stretch" in row:
        c = pb.constraints.new("STRETCH_TO")
        c.target = empty_at(host_point(row["stretch"]), f"stretch_{name}")
        c.rest_length = pb.bone.length
        c.volume = "NO_VOLUME"
    if "aim" in row:
        c = pb.constraints.new("DAMPED_TRACK")
        c.target = empty_at(host_point(row["aim"]), f"aim_{name}")
        c.track_axis = "TRACK_Y"
bpy.context.view_layer.update()

# report how close the fitted heads landed
worst = 0.0
for name, row in bmap.items():
    if "head" in row and name in src_arm.pose.bones:
        d = ((src_arm.matrix_world @ src_arm.pose.bones[name].head) - host_point(row["head"])).length
        worst = max(worst, d)
print(f"[rig] fitted bone heads within {worst * 100:.1f} cm of their host joints")

# ---- bake the fitted pose into the meshes, then move weights ---------------------------------------
for ob in src_meshes:
    bpy.context.view_layer.objects.active = ob
    for m in list(ob.modifiers):
        if m.type == "ARMATURE":
            bpy.ops.object.modifier_apply(modifier=m.name)
    mw = ob.matrix_world.copy()
    ob.parent = None
    ob.data.transform(mw)
    ob.matrix_world = Matrix.Identity(4)

    per_vertex = [dict() for _ in ob.data.vertices]
    groups = {g.index: g.name for g in ob.vertex_groups}
    for v in ob.data.vertices:
        for ge in v.groups:
            tgt = bmap[groups[ge.group]]["weights"]
            per_vertex[v.index][tgt] = per_vertex[v.index].get(tgt, 0.0) + ge.weight
    ob.vertex_groups.clear()
    new = {}
    for vi, ws in enumerate(per_vertex):
        total = sum(ws.values()) or 1.0
        for tgt, w in ws.items():
            g = new.get(tgt) or ob.vertex_groups.new(name=tgt)
            new[tgt] = g
            g.add([vi], w / total, "REPLACE")
    ob.parent = host_arm
    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = host_arm

unweighted = [ob.name for ob in src_meshes for v in ob.data.vertices if not v.groups]
print(f"[rig] {len(src_meshes)} meshes bound to {host_arm.name}; unweighted vertices: {len(unweighted)}")

# ---- clean up and export ---------------------------------------------------------------------------
bpy.data.objects.remove(src_arm)
for e in list(targets.objects):
    bpy.data.objects.remove(e)
bpy.data.collections.remove(targets)
host_arm.name = "Armature"
ref.hide_render = True
bpy.context.view_layer.layer_collection.children["host_ref"].exclude = True

os.makedirs(os.path.dirname(out_fbx), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.splitext(out_fbx)[0] + ".blend")
bpy.ops.object.select_all(action="DESELECT")
for o in [host_arm, *src_meshes]:
    o.select_set(True)
bpy.ops.export_scene.fbx(filepath=out_fbx, use_selection=True, add_leaf_bones=False, bake_anim=False,
                         use_armature_deform_only=False, path_mode="COPY", embed_textures=True,
                         mesh_smooth_type="FACE")
print(f"[rig] wrote {out_fbx}")
