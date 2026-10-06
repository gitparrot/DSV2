"""Blender script: place a rigid Dead Space 2 prop (a weapon) in a Vermintide 2 unit's own frame and export FBX.

    blender -b --factory-startup -P pipeline/place_prop.py -- ds2_export/pulse_rifle.blend ds2_export/pulse_rifle_1p.fbx
        --rotate-z 180 --offset 0.13,-0.23,-0.08

Weapon skins are linked by their root to the game weapon's root (weapon_skins.json link_nodes [[0, 0]]), so the model
must sit in that weapon's frame. The crank gun's root is its front grip (where the left hand attaches) with the
barrel along +Y and the muzzle at (0.13, 0.34, 0.05); the Pulse Rifle is modelled with its pistol grip at the origin
and the barrel along -Y. Rotating 180 about Z and offsetting puts its front grip on the left hand and lines the
muzzles up. Writes <out>.fbx, <out>.blend and the <out>.json sidecar that make_sdk_unit.py reads.
"""
import json, math, os, sys

import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
src, out_fbx = os.path.abspath(argv[0]), os.path.abspath(argv[1])
rot_z = float(argv[argv.index("--rotate-z") + 1]) if "--rotate-z" in argv else 0.0
offset = Vector([float(x) for x in argv[argv.index("--offset") + 1].split(",")]) if "--offset" in argv else Vector()

bpy.ops.wm.open_mainfile(filepath=src)
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
meshes = [o for o in bpy.data.objects if o.type == "MESH"]
arm.matrix_world = Matrix.Translation(offset) @ Matrix.Rotation(math.radians(rot_z), 4, "Z") @ arm.matrix_world
bpy.context.view_layer.update()

pts = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
lo = [round(min(p[i] for p in pts), 3) for i in range(3)]
hi = [round(max(p[i] for p in pts), 3) for i in range(3)]
print(f"[prop] placed: bounds {lo} .. {hi}")

os.makedirs(os.path.dirname(out_fbx), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.splitext(out_fbx)[0] + ".blend")
bpy.ops.object.select_all(action="DESELECT")
for o in [arm, *meshes]:
    o.select_set(True)
bpy.ops.export_scene.fbx(filepath=out_fbx, use_selection=True, add_leaf_bones=False, bake_anim=False,
                         use_armature_deform_only=False, path_mode="STRIP", embed_textures=False, mesh_smooth_type="FACE")
sidecar = {"armature": arm.name, "meshes": sorted(o.name for o in meshes),
           "materials": sorted({m.name for o in meshes for m in o.data.materials if m}), "weight_targets": []}
with open(os.path.splitext(out_fbx)[0] + ".json", "w", encoding="utf-8") as f:
    json.dump(sidecar, f, indent=1)
print(f"[prop] wrote {out_fbx}")
