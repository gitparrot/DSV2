# Steps on the Windows PC

Everything here needs the PC where Dead Space 2 and Vermintide 2 are installed. The easiest way is to run
Claude Code on that PC (https://claude.ai/download), open this repository there and say "continue the
Necromorph Tide pipeline". It can then run the tools below itself. Each step lists what it fills in the sheets.

## 1. Tools (free)
- **Warhammer: Vermintide 2 SDK**: Steam → Library → Tools.
- **Vermintide Mod Framework**: subscribe on the Workshop (https://steamcommunity.com/sharedfiles/filedetails/?id=1369573612)
  and keep it first in the launcher's mod list.
- **Vermintide Mod Builder (vmb)**: https://github.com/Vermintide-Mod-Framework/Vermintide-Mod-Builder/releases/latest
- **Blender**: https://www.blender.org/download/
- **Dead Space 2 extraction**: Gibbed.Visceral (https://github.com/gibbed/Gibbed.Visceral, source only: build
  `Gibbed.Visceral.sln` with Visual Studio's MSBuild) for `Gibbed.Visceral.StrUnpack.exe`, plus Blender and the
  `pipeline/ds2_*.py` scripts. Noesis (https://richwhitehouse.com/index.php?content=inc_projects.php) was installed
  but has no DS2 mesh reader; it's only an optional texture viewer.
- **Vermintide 2 skeletons**: Bitsquid Blender Tools (BBT) by qasikfwn
  (https://gitlab.com/qasikfwn/bitsquid-blender-tools/-/releases, needs Blender 5.2+), which unpacks VT2 bundles
  and imports units with their skeletons straight into Blender. VT2 Bundle Unpacker (gitlab.com/qasikfwn/vt2_bundle_unpacker)
  is the command-line alternative.

## 2. Create the Workshop item (private)
`vmb create dsv2`, then copy this repo's `mod/dsv2/` over the created folder. Keep `visibility = "private"` in
`itemV2.cfg`. Subscribe to the item it opens, then run `vmb build dsv2`. With no skins built yet, the mod
loads and does nothing. That's the first check: its options appear in the game's mod menu.

## 3. Get the Necromorphs out of Dead Space 2 (fills `source_models.ds2_archive`, `extracted`)
Proven on the Slasher (2026-10-05, see MODLOG). Noesis can't read DS2 meshes, so the route is Gibbed's
StrUnpack plus this repo's scripts. Run from the repo root; `<DS2>` is the Dead Space 2 folder, tools in `D:\Mods\tools`:
```
python pipeline/ds2_big_extract.py "<DS2>" DS2DAT6.DAT 0x258D62B5 -o extracted/ds2
Gibbed.Visceral.StrUnpack.exe extracted/ds2/DS2DAT6_258D62B5.str extracted/ds2/slasherhospital
python pipeline/ds2_tg4.py extracted/ds2/slasherhospital extracted/ds2/slasherhospital/dds
blender -b --factory-startup -P pipeline/ds2_to_fbx.py -- extracted/ds2/slasherhospital ds2_export/slasher.fbx --skeleton zombieb
```
The folder name passed to StrUnpack must be the character name (`slasherhospital`): the textures are
`<name>_c/_n/_sp`. To find another Necromorph, look for its `chars\<name>` / `char_str\npc\<name>_cct` strings in
DAT6-9 (MODLOG lists the names seen so far). Record the DAT and entry hash in `source_models.ds2_archive`.

## 4. Get each enemy's skeleton (fills `pipeline/bones/<breed>.txt`)
Proven on `chaos_fanatic`. The breed's bundle is the murmur64 of `resource_packages/breeds/<breed>` (look it up in
BBT's `unpacking/dictionary.csv`); extract only that enemy with BBT's bundled unpacker, then import with BBT:
```
unpacker.exe --dict dictionary.csv extract -i "units/beings/enemies/chaos_fanatic/*" "<VT2>/bundle/f46347ea8ad1569c" extracted/vt2
blender -b -P pipeline/vt2_bones.py -- extracted/vt2/units/beings/enemies/chaos_fanatic/chr_chaos_fanatic.unit pipeline/bones/chaos_fanatic.txt --blend extracted/vt2/chaos_fanatic.blend
```
(`unpacker.exe` and `dictionary.csv` are in BBT's `unpacking` folder; Blender runs without `--factory-startup` so
BBT is loaded.) The script writes the skin-weighted joints, one per line, and the full scene graph as comments.
The saved `.blend` is the skeleton to rig onto in step 5.

## 5. Rig and import (fills `enemy_skins.rigged`)
The skin must use the enemy's skeleton unchanged (the mod pins bone to bone). Import the enemy once more with BBT
**without** "Fix bone rotation", then fit the Necromorph onto it with a bone map (done for the Slasher):
```
blender -b -P pipeline/vt2_bones.py -- extracted/vt2/units/beings/enemies/chaos_fanatic/chr_chaos_fanatic.unit <scratch>.txt --no-fix --blend extracted/vt2/chaos_fanatic_nofix.blend
blender -b --factory-startup -P pipeline/rig_onto_host.py -- --source ds2_export/slasher.blend --host extracted/vt2/chaos_fanatic_nofix.blend --map pipeline/bone_maps/slasher_to_vt2_human.json --bones pipeline/bones/chaos_fanatic.txt --out ds2_export/slasher_fanatic.fbx
```
Other human-skeleton enemies (Marauder, Gor?) should reuse the same map with their own bones file. Then import
the FBX in the SDK as `units/dsv2/<id>/<id>` with its materials and set `rigged: true` in the sheet.

## 6. Generate, build, play (fills `tested_in_game`)
```
python tools/preflight.py
python tools/generate.py        (or --draft while some rows are unfinished)
lua5.1 tests/test_mod.lua
vmb build dsv2
```
Start Vermintide 2 in the **Modded Realm** and play a Chaos mission. The Fanatics should be Slashers.
Check the console log for `[dsv2]` warnings, then mark the row `tested_in_game: true`.

## Order
Slasher on the Chaos Fanatic first, all the way through. The rest repeat the same steps.
