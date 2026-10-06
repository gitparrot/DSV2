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

	local unit = { id = next_id, name = name, nodes = nodes or {}, data = data or {}, visible = true, alive = true, links = {}, scales = {} }

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
	set_local_scale = function (unit, node, scale) unit.scales[node] = scale end,
	-- skins come out of the SDK with x100 on the skeleton's rest pose (see dsv2.lua); hosts are unscaled
	world_pose = function (unit, node) return { x = { unit.rest_scale or 1, 0, 0 } } end,
}
Matrix4x4 = { x = function (m) return m.x end }
World = {
	spawn_unit = function (world, name)
		local skin = new_unit(name, { Hips = 1, Spine = 2 })

		skin.rest_scale = 100

		return skin
	end,
	link_unit = function (world, child, child_node, parent, parent_node)
		child.links[#child.links + 1] = { child_node, parent, parent_node }
	end,
	destroy_unit = function (world, unit) unit.alive = false end,
}
Vector3 = setmetatable({ length = function (v) return math.sqrt(v[1] ^ 2 + v[2] ^ 2 + v[3] ^ 2) end },
	{ __call = function (_, x, y, z) return { x, y, z } end })
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
-- like the game, unfreezing shows the unit through Unit.set_unit_visibility (looked up at call time: hooked by then)
BreedFreezer = { unfreeze_unit = function (self, unit) Unit.set_unit_visibility(unit, true) end }
PlayerUnitCosmeticExtension = { _init_mesh_attachment = function () end }
PlayerUnitFirstPerson = { init = function () end }
AttachmentUtils = { link = function () end }
AttachmentNodeLinking = { rotary_gun = { first_person = { wielded = { {} }, unwielded = { {} } }, third_person = { wielded = { {} } } } }
Managers.backend = { get_interface = function () return { get = function () return 2 end } end }

-- Mod framework stubs ------------------------------------------------------------------------------------
local settings = { faction_chaos = true, faction_skaven = false, marker_banner = true, isaac_engineer = true }
local warnings = {}
local infos = {}
local commands = {}
local echoes = {}
local mod = {
	info = function (self, fmt, ...) infos[#infos + 1] = string.format(fmt, ...) end,
	echo = function (self, fmt, ...) echoes[#echoes + 1] = string.format(fmt, ...) end,
	command = function (self, name, description, func) commands[name] = func end,
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
			careers = {
				dr_engineer = {
					third_person = { id = "isaac_3p", skin_unit = "units/dsv2/isaac_3p/isaac_3p", scale = 1,
						hide_inventory = false, setting = "isaac_engineer", links = { { "Hips", "Hips" } } },
					first_person = { id = "isaac_1p", skin_unit = "units/dsv2/isaac_1p/isaac_1p", scale = 1,
						hide_inventory = false, setting = "isaac_engineer", links = { { "Hips", "Hips" } } },
				},
			},
			weapons = {
				rotary_gun = {
					first_person = { id = "pulse_1p", skin_unit = "units/dsv2/pulse_1p/pulse_1p", scale = 1,
						hide_inventory = false, setting = "isaac_engineer", links = { { 0, 0 } } },
				},
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

function mod:hook(obj, method, handler)
	local original = obj[method]

	obj[method] = function (...)
		return handler(original, ...)
	end
	hooks[#hooks + 1] = method
end

get_mod = function (name) assert(name == "dsv2") return mod end

dofile("mod/dsv2/scripts/mods/dsv2/dsv2.lua")

-- Scenarios ----------------------------------------------------------------------------------------------
check(#hooks == 6, "six hooks registered (visibility, spawn, unfreeze, 3p mesh, 1p mesh, weapon link): " .. #hooks)

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
		if u.links[1] and u.links[1][2] == host and u.name:find("^units/dsv2/") then
			return u
		end
	end
end

local skin = skin_on(fanatic)

check(skin ~= nil and skin.name == "units/dsv2/slasher_fanatic/slasher_fanatic", "fanatic gets the Slasher skin")
check(skin and #skin.links == 3, "skin root linked, plus the two bones both skeletons share; missing bone skipped")
check(skin and skin.links[1][1] == 0 and skin.links[1][3] == 0, "skin root follows the host root (culling)")
check(skin and skin.visible == true, "skin visible while its enemy is hidden")
check(skin and skin.scales[1] and skin.scales[1][1] == 100 and skin.scales[2][1] == 100, "x100 rest scale restored on linked bones")
check(#infos == 2, "one info line per skin type the first time it is applied (" .. #infos .. ")")
check(fanatic.visible == false and axe.visible == false, "fanatic and its weapon hidden")
check(skin and skin.scales[0] and skin.scales[0][1] == 1.2, "sheet scale applied")
check(skin_on(slave) == nil and slave.visible, "Skaven toggle off: slave rat untouched")
check(skin_on(warrior) == nil and warrior.visible, "row without bones: warrior untouched")
check(skin_on(troll) == nil and troll.visible, "skin unit missing from bundle: troll untouched")
check(skin_on(clanrat) == nil and clanrat.visible, "breed without a row: clan rat untouched")
check(skin_on(banner) ~= nil and banner.visible == false, "placed banner becomes the Marker shard")
check(#warnings == 3, "one warning each for no bones, missing unit, missing bone (" .. #warnings .. ")")

mod.update(0.016)
check(#warnings == 3, "warnings are not repeated")

local freezer = { world = world }

Unit.set_unit_visibility(fanatic, false)
check(fanatic.visible == false and skin.visible == false, "the game hiding a skinned enemy (freezer) hides its skin")
BreedFreezer.unfreeze_unit(freezer, fanatic, "chaos_fanatic")
check(fanatic.visible == false and skin.visible == true, "reused from the pool: skin shown, original stays hidden")

local pooled = new_unit("chr_chaos_fanatic", { Hips = 10, Spine = 11 }, { breed = { name = "chaos_fanatic" } })

BreedFreezer.unfreeze_unit(freezer, pooled, "chaos_fanatic")
check(skin_on(pooled) ~= nil and pooled.visible == false, "pooled fanatic that never had a skin gets one when unfrozen")
BreedFreezer.unfreeze_unit(freezer, clanrat, "skaven_clan_rat")
check(skin_on(clanrat) == nil, "unfreezing a breed without a row does nothing")

-- hero meshes and weapons
local player = new_unit("player")
local tp_mesh = new_unit("chr_third_person_mesh", { Hips = 5 })
local fp_mesh = new_unit("chr_first_person_mesh", { Hips = 6 })
local hand = new_unit("first_person_base", { j_leftweaponattach = 3 })
local gun = new_unit("wpn_dw_rotary_gun_01_t1", { [0] = 0 })
local slayer_mesh = new_unit("chr_third_person_mesh", { Hips = 5 })

Unit.set_unit_visibility(tp_mesh, false) -- your own body is hidden in first person before the mod sees it
PlayerUnitCosmeticExtension._init_mesh_attachment({ _tp_unit_mesh = tp_mesh }, world, player, "skin", {}, { name = "dr_engineer" })
local isaac_3p = skin_on(tp_mesh)
check(isaac_3p ~= nil and isaac_3p.name == "units/dsv2/isaac_3p/isaac_3p", "Outcast Engineer's 3rd-person body gets Isaac")
check(tp_mesh.visible == false and isaac_3p.visible == false, "Isaac starts hidden like the body he replaces (first person)")
Unit.set_unit_visibility(tp_mesh, true)
check(tp_mesh.visible == false and isaac_3p.visible == true, "switching to 3rd person shows Isaac, not the dwarf")
PlayerUnitCosmeticExtension._init_mesh_attachment({ _tp_unit_mesh = slayer_mesh }, world, player, "skin", {}, { name = "dr_slayer" })
check(skin_on(slayer_mesh) == nil and slayer_mesh.visible, "other careers untouched")

PlayerUnitFirstPerson.init({ world = world, first_person_attachment_unit = fp_mesh }, {}, player,
	{ profile = { display_name = "dwarf_ranger", careers = { {}, { name = "dr_engineer" } } } })
check(skin_on(fp_mesh) ~= nil and fp_mesh.visible == false, "first-person arms get Isaac's (career from hero attributes)")

AttachmentUtils.link(world, hand, gun, AttachmentNodeLinking.rotary_gun.first_person.wielded)
local rifle = skin_on(gun)
check(rifle ~= nil and rifle.name == "units/dsv2/pulse_1p/pulse_1p" and gun.visible == false, "crank gun becomes the Pulse Rifle")
AttachmentUtils.link(world, hand, gun, AttachmentNodeLinking.rotary_gun.first_person.unwielded)
check(#rifle.links == 1, "re-linking the gun (holstered) does not add a second rifle")
AttachmentUtils.link(world, hand, new_unit("axe"), { {} })
gun.alive = false
mod.update(0.016)
check(not rifle.alive, "rifle removed once its gun is gone (sweep)")

commands.dsv2_status()
check(echoes[1] and echoes[1]:find("slasher_fanatic 2", 1, true) and echoes[1]:find("pulse_1p 1", 1, true),
	"/dsv2_status reports skins applied (" .. tostring(echoes[1]) .. ")")

UnitSpawner.create_unit_extensions(nil, world, fanatic, "ai_unit")
mod.update(0.016)
check(skin.alive, "a second pass does not double-skin or re-register the listener")

destroy_listeners[fanatic].dsv2_skin(fanatic)
check(not skin.alive, "skin destroyed with its enemy")

mod.on_game_state_changed("exit", "StateIngame")
check(true, "state change clears bookkeeping without error")

print(failures == 0 and "ALL PASSED" or (failures .. " FAILED"))
os.exit(failures == 0 and 0 or 1)
