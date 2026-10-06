# Necromorph Tide (private build)

A **personal, never-published** Vermintide 2 mod: Dead Space 2's Necromorphs replace Vermintide 2's enemies,
and Beastmen war banners become Marker shards.

> The Dead Space 2 models come from **your own copy** of Dead Space 2 and stay on your PC. They are git-ignored,
> never committed, and the Workshop item is set to **private**. Don't make it public or share the build.

## How it works
- Runs in Vermintide 2's **Modded Realm** through Fatshark's official SDK and the community Vermintide Mod
  Framework (VMF), so your official-realm account is never touched.
- Each enemy keeps its own AI, animations, hit zones and attacks. On your PC the mod hides the enemy's own
  model and attaches the Necromorph model to its skeleton. Nothing extra is sent over the network, so
  friends without the mod just see normal enemies.
- Expect jank: Necromorphs move with Vermintide skeletons, and dismemberment shows Vermintide gibs.

## Who becomes what
| Necromorph | Vermintide 2 enemies |
|---|---|
| Slasher | Chaos Fanatic, Chaos Marauder, Gor |
| The Pack | Slave Rat, Ungor |
| Twitcher | Plague Monk |
| Enhanced Slasher | Stormvermin, Chaos Raider |
| Leaper | Gutter Runner |
| Stalker | Bestigor |
| Exploder | Poison Wind Globadier |
| Puker | Warpfire Thrower |
| Lurker | Ratling Gunner |
| Spitter | Ungor Archer |
| Infector | Lifeleech |
| Brute | Minotaur, Rat Ogre |
| Tripod | Chaos Spawn |
| Ubermorph | Bile Troll |
| Divider | Chaos Warrior |
| Marker shard | the Beastmen Standard Bearer's planted banner |

Each faction and the banner can be toggled in the in-game mod options.

## Project layout
- `sheets/`: the design, the source of truth. One row per Necromorph model, enemy skin, prop, setting and game hook.
- `tools/preflight.py`: lists every unfilled cell, unverified check and broken reference across the sheets.
- `tools/generate.py`: turns the sheets into the mod's Lua data (`--draft` while cells are still unfilled).
- `mod/dsv2/`: the VMF mod (`dsv2.lua` is the hand-written logic; the other Lua files are generated).
- `tests/test_mod.lua`: runs the mod logic against a stubbed game (`lua5.1 tests/test_mod.lua`).
- `pipeline/PC_STEPS.md`: what has to happen on the Windows PC with both games installed.
- `MODLOG.md`: the journal: facts verified, open questions, next steps.

## Status
Source only, **not yet built or tested in game**. The code and data are written and logic-tested;
the models still have to be extracted, rigged and built on the PC. See `MODLOG.md`.
