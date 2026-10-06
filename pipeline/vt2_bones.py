"""Blender script: import a Vermintide 2 .unit with Bitsquid Blender Tools and write its bone names.

    blender -b -P pipeline/vt2_bones.py -- <extracted .unit> <pipeline/bones/<breed>.txt> [--blend out.blend] [--no-fix]

Needs Bitsquid Blender Tools (qasikfwn) enabled in this Blender (so no --factory-startup), and the unit
extracted beforehand with its bundled unpacker.exe, e.g.
    unpacker.exe --dict dictionary.csv extract -i "units/beings/enemies/chaos_fanatic/*" <VT2>/bundle/<hash> extracted/vt2
"Fix bone rotation" is on by default (PC_STEPS step 4); bone names are the same either way.
Output (pipeline/bones/README.md format): one bone per line = the joints the enemy's skin is weighted to,
then the full scene graph as # comments ("name<TAB>parent<TAB>joint|node[,skinned]").
"""
import os, sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
unit, out_txt = os.path.abspath(argv[0]), os.path.abspath(argv[1])
blend = os.path.abspath(argv[argv.index("--blend") + 1]) if "--blend" in argv else None

bpy.context.preferences.use_preferences_save = False  # the path below is for this run only
prefs = next(a.preferences for k, a in bpy.context.preferences.addons.items() if k.endswith("bitsquid"))
root = unit
while os.path.basename(root) != "units":  # the extraction root is the folder holding units/
    root = os.path.dirname(root)
prefs.extracted_files_dir_vt2 = os.path.dirname(root)


def import_armature(guess):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    st = bpy.context.scene.bitsquid_import_settings
    st.fix_bones = "--no-fix" not in argv
    st.fallback_bones = guess
    res = bpy.ops.import_scene.unit_vt2(filepath=unit)
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    if not arms:
        sys.exit(f"[vt2] no armature imported from {unit} ({res})")
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    return max(arms, key=lambda a: len(a.data.bones)), meshes


# The default import keeps only skinning joints and drops in-between scene-graph nodes (j_spine_scale,
# j_neck_scale, *_ref, *_end), orphaning their children. "Guess joints" rebuilds the whole tree.
arm, _ = import_armature(guess=False)
joints = {b.name for b in arm.data.bones}
arm, meshes = import_armature(guess=True)
weighted = {g.name for m in meshes for g in m.vertex_groups}
lines = []


def walk(b):
    kind = "joint" if b.name in joints else "node"
    if b.name in weighted:
        kind += ",skinned"
    lines.append("\t".join((b.name, b.parent.name if b.parent else "-", kind)))
    for c in sorted(b.children, key=lambda c: c.name):
        walk(c)


for r in sorted((b for b in arm.data.bones if not b.parent), key=lambda b: b.name):
    walk(r)
skinned = [ln.split("\t")[0] for ln in lines if ln.endswith(",skinned")]
os.makedirs(os.path.dirname(out_txt), exist_ok=True)
with open(out_txt, "w", encoding="utf-8", newline="\n") as f:
    f.write(f"# {os.path.basename(unit)} via Bitsquid Blender Tools 0.8.4, fix_bones={'--no-fix' not in argv}\n")
    f.write(f"# Bones to link (one per line): the {len(skinned)} joints the enemy's own skin is weighted to,\n"
            "# depth-first. Rig the Necromorph onto these.\n")
    f.write("\n".join(skinned) + "\n")
    f.write(f"#\n# Full scene graph ({len(lines)} nodes, {len(joints)} joints; 'Guess joints' import):\n"
            "# name<TAB>parent<TAB>joint|node[,skinned]\n")
    f.write("".join(f"# {ln}\n" for ln in lines))
print(f"[vt2] {len(lines)} nodes, {len(joints)} joints, {len(weighted)} skinned, {len(meshes)} meshes; wrote {out_txt}")
if blend:
    bpy.ops.wm.save_as_mainfile(filepath=blend)
