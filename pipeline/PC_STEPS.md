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
- **Dead Space 2 extraction**: Gibbed's Visceral BigViewer (DS2 build) + its .STR unpacker, then Noesis
  (https://richwhitehouse.com/index.php?content=inc_projects.php) to convert to FBX. See ResHax's
  "Dead Space Legacy (2008-2013) 3D Model Tools" thread for current downloads.
- **Vermintide 2 skeletons**: Bitsquid Blender Tools (BBT) by qasikfwn, which unpacks VT2 bundles and imports
  units with their skeletons straight into Blender. VT2 Bundle Unpacker (gitlab.com/qasikfwn/vt2_bundle_unpacker)
  is the command-line alternative.

## 2. Create the Workshop item (private)
`vmb create dsv2`, then copy this repo's `mod/dsv2/` over the created folder. Keep `visibility = "private"` in
`itemV2.cfg`. Subscribe to the item it opens, then run `vmb build dsv2`. With no skins built yet, the mod
loads and does nothing. That's the first check: its options appear in the game's mod menu.

## 3. Get the Necromorphs out of Dead Space 2 (fills `source_models.ds2_archive`, `extracted`)
Candidate route (community tutorials, not yet tried on this install): open the game's `.viv`/archive files
with the DS2 BigViewer, find the character folder under `global_assets`, extract the Necromorph's `.str`,
unpack it with the bundled .STR unpacker, then open the result in Noesis and export FBX to
`ds2_export/<id>.fbx` (git-ignored). Record the archive path in `source_models.ds2_archive`.
**Prove this with the Slasher first.**

## 4. Get each enemy's skeleton (fills `pipeline/bones/<breed>.txt`)
Candidate route: import the enemy's unit (e.g. `units/beings/enemies/chaos_fanatic/chr_chaos_fanatic`) into
Blender with Bitsquid Blender Tools, with bone-rotation fixing on. The armature gives both the bone names
for `pipeline/bones/<breed>.txt` and the skeleton to rig the Necromorph onto in step 5.
**Prove this on `chaos_fanatic` first.**

## 5. Rig and import (fills `enemy_skins.rigged`)
In Blender, fit the Necromorph over the enemy's skeleton, name the bones to match, weight it and export
an FBX. Import it in the SDK as `units/dsv2/<id>/<id>` with its materials. Set `rigged: true` in the sheet.

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
