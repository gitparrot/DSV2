-- Runs dsv2.lua against a stubbed game and mod framework to check its logic outside the game.
-- Run from the repo root: lua5.1 tests/test_mod.lua
-- This proves the bookkeeping (queue, skin, re-hide, cleanup), not the engine behaviour; that needs the game.

local failures = 0

local function check(condition, message)
	if condition then
		print("ok   " .. message)
	else
		failures = failures + 1
		print("FAIL " .. message)
	end
end

-- Engine stubs -------------------------------------------------------------------------------------------
local units = {}
local next_id = 0

local function new_unit(name, nodes, data)
	next_id = next_id + 1

	local unit = { id = next_id, name = name, nodes = nodes or {}, data = data or {}, visible = true, alive = true, links = {} }

	units[#units + 1] = unit

	return unit
end

Unit = {
	get_data = function (unit, key) return unit.data[key] end,
	alive = function (unit) return unit ~= nil and unit.alive end,
	set_unit_visibility = function (unit, visible) unit.visible = visible end,
	has_node = function (unit, name) return unit.nodes[name] ~= nil end,
	node = function (unit, name) return unit.nodes[name] end,
	world_position = function () return "pos" end,
	world_rotation = function () return "rot" end,
	set_local_scale = function (unit, node, scale) unit.scale = scale end,
}
World = {
	spawn_unit = function (world, name) return new_unit(name, { Hips = 1, Spine = 2 }) end,
	link_unit = function (world, child, child_node, parent, parent_node)
		child.links[#child.links + 1] = { child_node, parent, parent_node }
	end,
	destroy_unit = function (world, unit) unit.alive = false end,
}
Vector3 = function (x, y, z) return { x, y, z } end
Application = { can_get = function (kind, name) return kind == "unit" and name ~= "units/dsv2/missing/missing" end }

local inventories = {}

ScriptUnit = { has_extension = function (unit, system) return system == "ai_inventory_system" and inventories[unit] end }

local destroy_listeners = {}

Managers = {
	state = {
		unit_spawner = {
			add_destroy_listener = function (self, unit, identifier, callback)
				assert(not (destroy_listeners[unit] and destroy_listeners[unit][identifier]), "listener registered twice")
				destroy_listeners[unit] = destroy_listeners[unit] or {}
				destroy_listeners[unit][identifier] = callback
			end,
		},
	},
}
UnitSpawner = { create_unit_extensions = function () end }
BreedFreezer = { unfreeze_unit = function (self, unit) unit.visible = true end }

-- Mod framework stubs ------------------------------------------------------------------------------------
local settings = { faction_chaos = true, faction_skaven = false, marker_banner = true }
local warnings = {}
local mod = {
	get = function (self, id) return settings[id] end,
	warning = function (self, fmt, ...) warnings[#warnings + 1] = string.format(fmt, ...) end,
	dofile = function (self, path)
		return {
			breeds = {
				chaos_fanatic = { id = "slasher_fanatic", skin_unit = "units/dsv2/slasher_fanatic/slasher_fanatic", scale = 1.2,
					hide_inventory = true, setting = "faction_chaos", links = { { "Hips", "Hips" }, { "Spine", "Spine" }, { "Tail", "Tail" } } },
				skaven_slave = { id = "pack_slave", skin_unit = "units/dsv2/pack_slave/pack_slave", scale = 1,
					hide_inventory = true, setting = "faction_skaven", links = { { "Hips", "Hips" } } },
				chaos_warrior = { id = "divider_warrior", skin_unit = "units/dsv2/divider_warrior/divider_warrior", scale = 1,
					hide_inventory = true, setting = "faction_chaos", links = {} },
				chaos_troll = { id = "ubermorph_troll", skin_unit = "units/dsv2/missing/missing", scale = 1,
					hide_inventory = true, setting = "faction_chaos", links = { { "Hips", "Hips" } } },
			},
			templates = {
				standard_unit = { id = "marker_banner", skin_unit = "units/dsv2/marker_banner/marker_banner", scale = 1,
					hide_inventory = false, setting = "marker_banner", links = { { 0, 0 } } },
			},
		}
	end,
}
local hooks = {}

function mod:hook_safe(obj, method, handler)
	local original = obj[method]

	obj[method] = function (...)
		local a, b, c = original(...)

		handler(...)

		return a, b, c
	end
	hooks[#hooks + 1] = method
end

get_mod = function (name) assert(name == "dsv2") return mod end

dofile("mod/dsv2/scripts/mods/dsv2/dsv2.lua")

-- Scenarios ----------------------------------------------------------------------------------------------
check(#hooks == 2, "two hooks registered (create_unit_extensions, unfreeze_unit)")

local world = "level_world"
local fanatic = new_unit("chr_chaos_fanatic", { Hips = 10, Spine = 11 }, { breed = { name = "chaos_fanatic" } })
local axe = new_unit("axe")

inventories[fanatic] = { inventory_item_units = { axe } }

local slave = new_unit("chr_skaven_slave", { Hips = 10 }, { breed = { name = "skaven_slave" } })
local warrior = new_unit("chr_chaos_warrior", { Hips = 10 }, { breed = { name = "chaos_warrior" } })
local troll = new_unit("chr_chaos_troll", { Hips = 10 }, { breed = { name = "chaos_troll" } })
local clanrat = new_unit("chr_skaven_clan_rat", { Hips = 10 }, { breed = { name = "skaven_clan_rat" } })
local banner = new_unit("wpn_bm_standard_01_placed", { [0] = 0 })

for _, u in ipairs({ fanatic, slave, warrior, troll, clanrat }) do
	UnitSpawner.create_unit_extensions(nil, world, u, "ai_unit_" .. u.name)
end

UnitSpawner.create_unit_extensions(nil, world, banner, "standard_unit")
check(#units == 7, "nothing spawned before the next update")

mod.update(0.016)

local function skin_on(host)
	for _, u in ipairs(units) do
		if u.links[1] and u.links[1][2] == host then
			return u
		end
	end
end

local skin = skin_on(fanatic)

check(skin ~= nil and skin.name == "units/dsv2/slasher_fanatic/slasher_fanatic", "fanatic gets the Slasher skin")
check(skin and #skin.links == 2, "skin linked on the two bones both skeletons share; missing bone skipped")
check(fanatic.visible == false and axe.visible == false, "fanatic and its weapon hidden")
check(skin and skin.scale and skin.scale[1] == 1.2, "sheet scale applied")
check(skin_on(slave) == nil and slave.visible, "Skaven toggle off: slave rat untouched")
check(skin_on(warrior) == nil and warrior.visible, "row without bones: warrior untouched")
check(skin_on(troll) == nil and troll.visible, "skin unit missing from bundle: troll untouched")
check(skin_on(clanrat) == nil and clanrat.visible, "breed without a row: clan rat untouched")
check(skin_on(banner) ~= nil and banner.visible == false, "placed banner becomes the Marker shard")
check(#warnings == 3, "one warning each for no bones, missing unit, missing bone (" .. #warnings .. ")")

mod.update(0.016)
check(#warnings == 3, "warnings are not repeated")

BreedFreezer.unfreeze_unit(nil, fanatic, "chaos_fanatic")
check(fanatic.visible == false, "re-hidden after the pool reuses it")

UnitSpawner.create_unit_extensions(nil, world, fanatic, "ai_unit")
mod.update(0.016)
check(skin.alive, "a second pass does not double-skin or re-register the listener")

destroy_listeners[fanatic].dsv2_skin(fanatic)
check(not skin.alive, "skin destroyed with its enemy")

mod.on_game_state_changed("exit", "StateIngame")
check(true, "state change clears bookkeeping without error")

print(failures == 0 and "ALL PASSED" or (failures .. " FAILED"))
os.exit(failures == 0 and 0 or 1)
