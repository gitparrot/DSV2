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

## Open questions (block the first in-game build)
1. A Dead Space 2 model extractor that works on the current Steam/EA build (pipeline step 3).
2. How to read Vermintide 2 enemy skeleton bone names (pipeline step 4).
3. In game: does `Unit.set_unit_visibility(false)` survive hit flashes and flow events? Does a linked skin
   follow bone scale on dismemberment?

## Not in this version
- The carried (unplanted) banner keeps its Beastmen look; only the planted banner becomes a Marker.
- Plasma cutter, Isaac's suit and Dead Space sounds: discussed, not started.
