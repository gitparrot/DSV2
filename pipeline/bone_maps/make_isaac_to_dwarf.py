"""Write the bone maps that fit Isaac (Dead Space 2 "player" skeleton) onto Bardin the Outcast Engineer.

    python pipeline/bone_maps/make_isaac_to_dwarf.py extracted/ds2/isaac_engineering extracted/ds2/global_assets

Writes isaac_to_vt2_dwarf_3p.json (third-person body, j_* human-style dwarf skeleton) and
isaac_to_vt2_dwarf_1p.json (first-person arms only). Build Isaac at real size first (ds2_to_fbx.py --scale 1.8):
the fit then shortens his legs to dwarf height while keeping his width, which matches Bardin's shoulders.

Isaac's joints, as found (pipeline/ds2_bone_names.txt): the "Twist" joints are the limb segments
(L_hipTwist = thigh, L_shoulderTwist = upper arm), l_elbow = forearm, m_neck2 = head. Unnamed joints keep their
rcb index: bone_06/11/16 spine, bone_17-22 back meter, bone_28 chest, bone_09/10... belt, the rest face/RIG
details; they follow their nearest named ancestor.
"""
import collections, json, os, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import ds2_geo  # noqa: E402

mesh_src, rcb_src = sys.argv[1], sys.argv[2]
skel = next(s for f in sorted(os.listdir(os.path.join(rcb_src, "RCB")))
            for s in ds2_geo.read_rcb(open(os.path.join(rcb_src, "RCB", f), "rb").read())["skeletons"] if s["name"] == "player")
n = len(skel["parents"])
hashes = {}
for g in ds2_geo.load_stream_geos(mesh_src).values():
    if g["bones"] and max(b["rcb_index"] for b in g["bones"]) < n and len(g["bones"]) >= n - 2:
        hashes.update({b["rcb_index"]: b["hash"] for b in g["bones"]})
known = [l.strip() for l in open(os.path.join(os.path.dirname(__file__), "..", "ds2_bone_names.txt"), encoding="utf-8")
         if l.strip() and not l.startswith("#")]
table = {ds2_geo.name_hash(w): w for w in known}
names = [table.get(hashes.get(i), f"bone_{i:02d}") for i in range(n)]
parent = {names[i]: (names[p] if p >= 0 else None) for i, p in enumerate(skel["parents"])}
low = {nm.lower(): nm for nm in names}  # the found names have mixed case (L_knee, r_knee)
J = lambda x: low[x.lower()]  # Isaac joint by case-insensitive name


def build(view):
    first = view == "1p"
    W = collections.OrderedDict()  # Isaac joint -> dwarf joint(s) for weights
    fit = {}
    for s, side in (("l", "left"), ("r", "right")):
        roll_arm = [f"j_{side}arm_roll", f"j_{side}armroll", f"j_{side}arm"]
        roll_fore = [f"j_{side}forearm_roll", f"j_{side}forearmroll", f"j_{side}forearm"]
        W[J(f"{s}_clav")] = f"j_{side}shoulder"
        W[J(f"{s}_shoulder")] = f"j_{side}arm"
        W[J(f"{s}_shoulderTwist")] = f"j_{side}arm"
        W[J(f"{s}_elbow")] = f"j_{side}forearm"
        W[J(f"{s}_elbowTwist")] = roll_fore
        W[J(f"{s}_wrist")] = f"j_{side}hand"
        W[J(f"{s}_weapon")] = f"j_{side}hand"
        for ds, vt in (("finger", "middle"), ("index", "index"), ("pinky", "pinky"), ("ring", "ring"), ("thumb", "thumb")):
            for i in (1, 2, 3):
                if f"{s}_{ds}{i}" in low:
                    W[J(f"{s}_{ds}{i}")] = ([f"j_{side}hand{vt}{i}"] if first else []) + [f"j_{side}hand"]
        fit[J(f"{s}_clav")] = dict(head=f"j_{side}shoulder", stretch=f"j_{side}arm", tail_to=J(f"{s}_shoulder"))
        fit[J(f"{s}_shoulderTwist")] = dict(head=f"j_{side}arm", stretch=f"j_{side}forearm", tail_to=J(f"{s}_elbow"))
        fit[J(f"{s}_elbow")] = dict(head=f"j_{side}forearm", stretch=f"j_{side}hand", tail_to=J(f"{s}_wrist"))
        fit[J(f"{s}_wrist")] = dict(head=f"j_{side}hand", rigid=True)
        if not first:
            W[J(f"{s}_hip")] = f"j_{side}upleg"
            W[J(f"{s}_hipTwist")] = f"j_{side}upleg"
            W[J(f"{s}_knee")] = f"j_{side}leg"
            W[J(f"{s}_kneeTwist")] = [f"j_{side}leg_roll", f"j_{side}leg"]
            W[J(f"{s}_ankle")] = f"j_{side}foot"
            W[J(f"{s}_ball")] = f"j_{side}toebase"
            fit[J(f"{s}_hipTwist")] = dict(head=f"j_{side}upleg", stretch=f"j_{side}leg", tail_to=J(f"{s}_knee"))
            fit[J(f"{s}_knee")] = dict(head=f"j_{side}leg", stretch=f"j_{side}foot", tail_to=J(f"{s}_kneeTwist"))
            fit[J(f"{s}_ankle")] = dict(head=f"j_{side}foot", aim=f"j_{side}toebase", tail_to=J(f"{s}_ball"), rigid=True)
    if first:  # the arms only: everything else rides on the shoulders (its meshes are left out of the 1p FBX)
        body = "j_rightshoulder"
        for nm in names:
            W.setdefault(nm, None)
    else:
        W.update({"m_root": "j_hips", "m_camera": "j_hips", "m_pelvis": "j_hips", "bone_06": "j_spine",
                  "bone_11": "j_spine1", "bone_16": "j_spine2", "m_neck1": "j_neck", "bone_39": "j_neck",
                  "m_neck2": "j_head", "m_jaw": ["j_jaw_anim", "j_head"], "m_chin": "j_head"})
        fit.update({"m_pelvis": dict(head="j_hips"),
                    "bone_06": dict(head="j_spine", stretch="j_spine1", tail_to="bone_11"),
                    "bone_11": dict(head="j_spine1", stretch="j_spine2", tail_to="bone_16"),
                    "bone_16": dict(head="j_spine2", stretch="j_neck", tail_to="m_neck1"),
                    "m_neck1": dict(head="j_neck", stretch="j_head", tail_to="m_neck2"),
                    "m_neck2": dict(head="j_head", rigid=True)})
    bones = collections.OrderedDict()
    for nm in names:
        w = W.get(nm)
        p = nm
        while w is None and p is not None:  # unnamed details follow their nearest mapped ancestor
            p = parent[p]
            w = W.get(p) if p else None
        bones[nm] = {"weights": w if w is not None else (body if first else "j_hips")}
        bones[nm].update(fit.get(nm, {}))
    if first:  # in the 1p map only the arms are fitted; the rest stays put
        for nm in names:
            if not any(k in nm.lower() for k in ("clav", "shoulder", "elbow", "wrist", "finger", "index", "pinky", "ring", "thumb", "weapon")):
                bones[nm] = {"weights": body}
    return bones


base = json.load(open(os.path.join(os.path.dirname(__file__), "slasher_to_vt2_human.json"), encoding="utf-8"))
for view, label in (("3p", "third-person body"), ("1p", "first-person arms")):
    out = {"about": f"How rig_onto_host.py fits Isaac (Dead Space 2 'player' skeleton, built with --scale 1.8) onto Bardin "
                    f"the Outcast Engineer's {label}. Generated by make_isaac_to_dwarf.py; edit that script, not this file.",
           "fields": base["fields"], "rotate_z_degrees": 180, "bones": build(view)}
    path = os.path.join(os.path.dirname(__file__), f"isaac_to_vt2_dwarf_{view}.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(out, indent=1) + "\n")
    print(f"wrote {path}: {len(out['bones'])} rows")
