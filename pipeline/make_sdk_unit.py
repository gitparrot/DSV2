"""Write a Vermintide 2 SDK unit for a rigged skin: <id>.unit, <id>.material and three .texture files.

    python pipeline/make_sdk_unit.py --id slasher_fanatic --fbx ds2_export/slasher_fanatic.fbx
        --textures extracted/ds2/slasherhospital/dds/slasherhospital --mod mod/dsv2

Layout written under <mod>/units/dsv2/<id>/ (resource name units/dsv2/<id>/<id>, as in sheets/enemy_skins.json):
  <id>.unit, <id>.material, <id>_df/_nm/_sp.texture   our text files, committed
  <id>.fbx, <id>_df/_nm/_sp.png                         copied from git-ignored exports, never committed
(the SDK only takes uncompressed texture sources, hence PNG from pipeline/ds2_tg4.py --png)
The SDK compiler imports the .fbx that shares the unit's name (skinned; it has its own FBX importer).
Mesh and material names come from the <fbx>.json sidecar written by pipeline/rig_onto_host.py.
Material: core standard_base (skinned by default) with base colour = _c (sRGB), normal = _n
(DXT5_NM: X in alpha, Y in green, Z rebuilt by decode_normal; plain RGB normal maps per the formats.json that
ds2_tg4.py writes), roughness = 1 - _sp.r.
"""
import argparse, difflib, json, os, shutil, uuid

UV, DF, NM, SP, DEC, INV, OUT = (str(uuid.uuid5(uuid.NAMESPACE_URL, f"dsv2/{n}")) for n in
                                 ("uv", "df", "nm", "sp", "decode", "invert", "out"))
OPT = {"wrap": "5dd59b3d-1762-4a14-9930-7500230ef3db", "aniso": "1e067464-12d8-4826-9b72-cfd5765003e3",
       "aniso8": "c05701f4-270c-4d7b-abd3-9d4917a4e4cb", "srgb": "fb3f709b-a54a-4e93-ac9f-e9fc76fb8bcd",
       "linear": "e94e53e6-49b6-4194-a747-8f064a5932e0"}
IN = {"texcoord": "1ee9af1f-65f2-4739-ad28-5ea6a0e68fc3", "base_color": "aca690cb-6305-4a2f-bf3d-69183a493db3",
      "normal": "b1c86408-aacb-4466-b754-ddcf37a3a2c8", "roughness": "36ba46d2-f6ea-4e60-a428-fdc17c75bc62",
      "normal2": "e796d926-3c92-46c5-8aa4-0351529e310e", "normal3": "e53657b4-36f9-48d5-8bfd-572552b56fdf", "invert_a": "DB6BAC1D-3931-42BD-BD08-829BFBCBAD47"}


def sjson(v, ind=0):
    """Minimal SJSON writer in the SDK's own style (tabs, no commas)."""
    t = "\t" * ind
    if isinstance(v, dict):
        return "{\n" + "".join(f"{t}\t{k} = {sjson(x, ind + 1)}\n" for k, x in v.items()) + t + "}"
    if isinstance(v, list):
        return "[\n" + "".join(f"{t}\t{sjson(x, ind + 1)}\n" for x in v) + t + "]"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return json.dumps(v)
    return repr(v)


def top(d):
    return "".join(f"{k} = {sjson(v)}\n" for k, v in d.items())


def link(src, dst, connector, select=None):
    c = {"destination": {"connector_id": connector, "instance_id": dst}, "source": {"instance_id": src}}
    if select:
        c["select"] = [select]
    return c


def node(nid, kind, x, y, options=(), samplers=None, title=None):
    n = {"content_size": [160, 0], "export": {}, "id": nid, "options": list(options), "position": [x, y],
         "samplers": samplers or {}, "type": kind}
    if title:
        n["title"] = title
    return n


def sampler(nid, slot, title, encoding, y):
    return node(nid, "core/shader_nodes/sample_texture", -140, y, (OPT["wrap"], encoding, OPT["aniso"], OPT["aniso8"]),
                {"texture_map": {"display_name": title, "slot_name": slot, "sort_tag": -1}}, title)


def material(res_dir, ident, normal_fmt="DXT5_NM"):
    slots = {"texture_map_df": f"{res_dir}/{ident}_df", "texture_map_nm": f"{res_dir}/{ident}_nm",
             "texture_map_sp": f"{res_dir}/{ident}_sp"}
    nodes = [node(UV, "core/shader_nodes/texture_coordinate0", -460, 260),
             sampler(DF, "texture_map_df", "Base colour", OPT["srgb"], 100),
             sampler(NM, "texture_map_nm", "Normal (DXT5_NM)", OPT["linear"], 200),
             sampler(SP, "texture_map_sp", "Specular", OPT["linear"], 300),
             node(DEC, "core/shader_nodes/decode_normal", 100, 200),
             node(INV, "core/shader_nodes/invert", 100, 300),
             node(OUT, "core/stingray_renderer/output_nodes/standard_base", 400, 200)]
    conns = [link(UV, s, IN["texcoord"]) for s in (DF, NM, SP)]
    nm_link = link(NM, DEC, IN["normal2"], "ag") if normal_fmt.endswith("_NM") else link(NM, DEC, IN["normal3"], "rgb")
    conns += [link(DF, OUT, IN["base_color"], "rgb"), nm_link,
              link(DEC, OUT, IN["normal"]), link(SP, INV, IN["invert_a"], "r"), link(INV, OUT, IN["roughness"])]
    return top({"material_contexts": {"surface_material": "flesh"},
                "shader": {"connections": conns, "constants": [], "nodes": nodes, "version": 2},
                "textures": slots, "variables": {}})


def texture(res_path, fmt, srgb):
    return top({"common": {"input": {"filename": res_path},
                           "output": {"apply_processing": True, "cut_alpha_threshold": 0.5,
                                      "enable_cut_alpha_threshold": False, "format": fmt, "mipmap_filter": "kaiser",
                                      "mipmap_filter_wrap_mode": "mirror", "mipmap_keep_original": False,
                                      "mipmap_num_largest_steps_to_discard": 0,
                                      "mipmap_num_smallest_steps_to_discard": 0, "srgb": srgb,
                                      "streamable": False}}})


def unit(meshes, mat_res_of):
    rend = {m: {"always_keep": False, "culling": "bounding_volume", "generate_uv_unwrap": False, "occluder": False,
                "shadow_caster": True, "surface_queries": False, "viewport_visible": True} for m in meshes}
    return top({"materials": dict(mat_res_of), "renderables": rend})


def find_png(tex_dir, texture_set, suffixes):
    """<set>_<suffix>.png, trying suffixes in order; else the closest file name (Isaac's helmet colour map is spelt
    "playermnerhelmet_c"; the Pulse Rifle's material is "pulserifle" for files named "pulse_rifle_*")."""
    for sfx in suffixes:
        p = os.path.join(tex_dir, f"{texture_set}_{sfx}.png")
        if os.path.exists(p):
            return p
    pngs = [f[:-4] for f in os.listdir(tex_dir) if f.endswith(".png")]
    for sfx in suffixes:
        close = difflib.get_close_matches(f"{texture_set}_{sfx}", [f for f in pngs if f.endswith(f"_{sfx}")], 1, 0.8)
        if close:
            return os.path.join(tex_dir, close[0] + ".png")
    raise FileNotFoundError(f"no {texture_set}_{'/'.join(suffixes)}.png in {tex_dir}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--fbx", required=True)
    ap.add_argument("--textures", required=True,
                    help="folder of <set>_c/_n/_sp.png (ds2_tg4.py --png); a <folder>/<set> prefix also works")
    ap.add_argument("--mod", required=True, help="mod source root (folder with the .mod file)")
    a = ap.parse_args()
    info = json.load(open(os.path.splitext(a.fbx)[0] + ".json", encoding="utf-8"))
    tex_dir = a.textures if os.path.isdir(a.textures) else os.path.dirname(a.textures)
    res_dir = f"units/dsv2/{a.id}"
    out = os.path.join(a.mod, *res_dir.split("/"))
    os.makedirs(out, exist_ok=True)
    w = lambda name, text: open(os.path.join(out, name), "w", encoding="utf-8", newline="\n").write(text)
    fmt_path = os.path.join(tex_dir, "formats.json")
    formats = json.load(open(fmt_path)) if os.path.exists(fmt_path) else {}
    # one material per texture set (the FBX's material names are the sets); a single set keeps the plain <id> names
    materials = info["materials"]
    mat_res_of = {}
    for texture_set in materials:
        ident = a.id if len(materials) == 1 else f"{a.id}_{texture_set}"
        mat_res_of[texture_set] = f"{res_dir}/{ident}"
        normal_png = find_png(tex_dir, texture_set, ("n",))
        normal_fmt = formats.get(os.path.basename(normal_png)[:-4], "DXT5_NM")
        w(f"{ident}.material", material(res_dir, ident, normal_fmt))
        for suffix, srcs, fmt, srgb in (("df", ("c", "ca"), "DXT1", True), ("nm", ("n",), "DXT5", False),
                                         ("sp", ("sp", "s", "sc"), "DXT1", False)):
            w(f"{ident}_{suffix}.texture", texture(f"{res_dir}/{ident}_{suffix}", fmt, srgb))
            shutil.copyfile(find_png(tex_dir, texture_set, srcs), os.path.join(out, f"{ident}_{suffix}.png"))
    w(f"{a.id}.unit", unit(info["meshes"], mat_res_of))
    shutil.copyfile(a.fbx, os.path.join(out, f"{a.id}.fbx"))
    print(f"wrote {res_dir}/{a.id}.unit (+ {len(materials)} material(s), {3 * len(materials)} textures; "
          f"fbx/png copied, git-ignored) in {a.mod}")


if __name__ == "__main__":
    main()
