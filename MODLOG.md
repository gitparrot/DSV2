# MODLOG: Necromorph Tide

## Decisions
- Private, never published. Melty listing dropped at the owner's request (2026-10-06).
- Host: Vermintide 2 (Stingray/Bitsquid, Lua), Modded Realm, official SDK + VMF. Dead Space 2 supplies models.
- Route: a visual swap per player (hide the host model, link the skin to its skeleton), **not** replacing
  `breed.base_unit`. Reason: enemies spawn as network units whose names travel as `NetworkLookup.husks`
  indexes (vt2src scripts/network_lookup/network_lookup.lua:331). A new unit name there would break co-op
  and players without the mod.

## Verified in the game's Lua (vt2src = github.com/Aussiemon/Vermintide-2-Source-Code)
- Enemies spawn from `breed.base_unit` (PC) in conflict_director.lua:1906; `opt_base_unit` is console only (boot.lua:304).
- All enemy spawns, host and client husks, run `UnitSpawner.create_unit_extensions` (unit_spawner.lua:309, 326, 470).
- The breed is on the unit as `Unit.get_data(unit, "breed")`: host via ai_simple_extension.lua:25, husk via
  game_object_initializers_extractors.lua:13.
- Enemies are pooled: the freezer hides them (breed_freezer.lua:348) and `unfreeze_unit` shows them again (:465).
- Dismemberment scales host bones to zero (flow_callbacks_enemy.lua:127), which should also hide the linked skin's limb.
- Placed banner: `wpn_bm_standard_01_placed`, unit template `standard_unit` (bt_place_standard_action.lua:118-119).
- The breed `base_unit` paths in sheets/enemy_skins.json are copied from each breed file (line given per row).

## Done here (cloud session, no games available)
- Sheets, preflight, generator, VMF mod source, Lua syntax check (lua5.1) and a stubbed logic test: 17/17 pass.

## Done on the PC (2026-10-05, Claude Code on the owner's Windows PC)
Installs: Steam `Dead Space 2` (app 47780) at `C:\Program Files (x86)\Steam\steamapps\common\Dead Space 2`;
`Warhammer: Vermintide 2` (app 552500) at `D:\SteamLibrary\steamapps\common\Warhammer Vermintide 2`.
Tools (owner approved; all outside the repo in `D:\Mods\tools`): Gibbed.Visceral (github.com/gibbed/Gibbed.Visceral,
source only, built with VS2019 MSBuild), Noesis 4.474 (richwhitehouse.com), Blender 5.2.2 portable (blender.org,
SHA-256 checked), Bitsquid Blender Tools 0.8.4 (gitlab.com/qasikfwn/bitsquid-blender-tools; Blender extension in
`%APPDATA%\Blender Foundation\Blender\5.2\extensions`). Nothing was written to either game folder.

**Step 3, Slasher: works, but not by the route in the tutorials.** `ds2_export/slasher.fbx` (git-ignored) re-opens in a
clean Blender with 10 mesh pieces (~6k tris), a 51-bone armature with the original joint names, full skin weights
and its 1024² textures; a posed test render deforms correctly.
- Archives: the Steam build has no `.viv` files. `DS2DAT{0,1,6,7,8,9}.DAT` are BIGH archives (layout as Gibbed's
  `BigFile.cs`; entries stored raw, so `pipeline/ds2_big_extract.py` copies one out exactly like BigViewer's save).
  Character streams live in DAT6-9 under `levels\global_assets\...\char_str\npc\<name>_cct\`.
- Slasher = `chars\slasherhospital`, inside `DS2DAT6.DAT` entry `0x258D62B5` (the ch01_hos stream). Other Slasher
  skins: `slashermzipper`, `slasherfemeyes` (DAT6 0x61875FF6), `slasherbully` (DAT9 0xAE3E625E), `slashersecurity`,
  `slasher_woman` / `slasher_fem_civilian` / `slasher_fem_eyes` (DAT9 zomb_cct). All share skeleton `zombieb`.
  Enhanced Slasher = `chars\superslasher`, DAT9 entry `0xCDE7B5D8` (filled in the sheet, not extracted yet).
- Gibbed `StrUnpack` works on the stream (Mesh, MeshVolatile, RCB, HKX, Material, tg4h/tg4d folders).
- **Failed / not usable:** Gibbed `BigViewer` is GUI-only (bypassed by the script above). Gibbed `ConvertTG4` is a
  hard-coded test stub. **Noesis has no Dead Space 2 mesh format**; per the ResHax "Dead Space Legacy" thread and the
  ZenHAX tutorial, DS2 meshes are read by 3ds Max scripts (no 3ds Max here) and Noesis only does textures.
  MeltyTool (ex-FinModelUtility, GPL-3) has .geo/.rcb readers, but its DS2 module is an unlisted stub.
- What worked instead: `pipeline/ds2_geo.py` (ported from MeltyTool's readers, so GPL-3) + `pipeline/ds2_tg4.py`
  + `pipeline/ds2_to_fbx.py` in Blender. DS2 PC layout facts found on the Slasher:
  - each `.geo` is split by StrUnpack into `Mesh/` + `MeshVolatile/`; the header length (0x0C) = both joined;
  - bones in `.geo` are (Visceral name hash, rcb index) pairs, not strings; the names come from the `.hkx.win`
    Havok file (`Deform_m_root`, ...), matched with Gibbed's hash (lowercase, h*65599+c): 51/51 matched;
  - `.rcb` holds the hierarchy and inverse bind matrices (row-major); skeletons `zombie` and `zombieb`;
  - vertex 32 B (pos, packed normal, packed tangent, 4 palette slots, 4 u16 weights); rigid pieces (claws) 20 B,
    bound to palette[0]; flags 0xF0000 = influences per vertex; UVs in a separate stride-8 buffer;
  - `.tg4h` = width/height/mips + format tag (DXT1c, DXT5_NM...), `.tg4d` = raw DXT mip chain;
  - `lodmodel.geo` is an unskinned far LOD with another layout (skipped).
- The model is the whole Slasher built from its dismemberment pieces (`mesh_*_dism`); the `_pc`/`_sc` wound caps are
  left out (`--caps` adds them).

**Step 4, Chaos Fanatic: works.** `pipeline/bones/chaos_fanatic.txt` lists the 99 joints its skin is weighted to,
plus the full 168-node scene graph as comments.
- `chr_chaos_fanatic.unit`/`.bones` come out of bundle `f46347ea8ad1569c` (= murmur of
  `resource_packages/breeds/chaos_fanatic`) with BBT's bundled `unpacker.exe --dict dictionary.csv extract -i ...`.
- BBT's import needs its "VT2 extracted files directory" preference; `pipeline/vt2_bones.py` sets it per run.
- **Pitfall:** BBT's default import drops in-between scene-graph nodes (`j_spine_scale`, `j_neck_scale`, `*_ref`,
  `*_end`) and leaves 32 root bones (e.g. `j_head` unparented). "Guess joints" (`fallback_bones`) rebuilds the real
  tree: `root_point > j_hips > j_spine > j_spine_scale > j_spine1 > ...`, 1 root. The script uses both imports.
- `generate.py` now emits the Fanatic's 99 links (`dsv2_skins.lua`).

## Open questions (block the first in-game build)
1. Rigging (step 5): the Slasher is 2.15 m in a T-pose facing -Y; the Fanatic is 1.9 m in an A-pose facing +Y.
   Fit, rename and reweight onto the 99 Fanatic joints. The DXT5_NM normal map is wired in `slasher.blend` but does
   not survive the FBX export (base colour and specular do).
2. `tests/test_mod.lua` was not re-run on the PC (no Lua 5.1 here); the change is generated data only.
3. Other Necromorphs: `char_str\npc` names seen in DAT6-9, mapping still to confirm: `div` (Divider?), `exp`
   (Exploder?), `inf` (Infector?), `leap` (Leaper?), `pack_boy`/`pack_girl` (The Pack), `stalker`, `tripod`, `pois`,
   `guarpd`, `kong`, `corbod`, `swrm`, `flier`, `preg`. Twitcher, Lurker, Spitter, Brute, Ubermorph, Marker not found
   by name yet (the scan only read the first 256 KB of each entry).
4. In game: does `Unit.set_unit_visibility(false)` survive hit flashes and flow events? Does a linked skin
   follow bone scale on dismemberment?

## Not in this version
- The carried (unplanted) banner keeps its Beastmen look; only the planted banner becomes a Marker.
- Plasma cutter, Isaac's suit and Dead Space sounds: discussed, not started.
