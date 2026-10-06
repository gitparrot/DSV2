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
- **A Dead Space 2 model extractor**: still to be found (step 3).

## 2. Create the Workshop item (private)
`vmb create dsv2`, then copy this repo's `mod/dsv2/` over the created folder. Keep `visibility = "private"` in
`itemV2.cfg`. Subscribe to the item it opens, then run `vmb build dsv2`. With no skins built yet, the mod
loads and does nothing. That's the first check: its options appear in the game's mod menu.

## 3. Get the Necromorphs out of Dead Space 2 (fills `source_models.ds2_archive`, `extracted`)
Find which archive in the Dead Space 2 folder holds each model and a tool that exports it, for example
a Noesis plugin or a community script. Export each model to `ds2_export/<id>.fbx`; that folder is git-ignored.
**Unknown: no current, documented tool was found yet. This is the first thing to prove, with the Slasher.**

## 4. Get each enemy's skeleton (fills `pipeline/bones/<breed>.txt`)
We need the bone names of each Vermintide enemy so the Necromorph can be weighted to them.
**Unknown: how to read Vermintide 2's enemy skeletons (an SDK sample, a community unbundler, or a debug
dump in game). Prove this on `chaos_fanatic` first.**

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
