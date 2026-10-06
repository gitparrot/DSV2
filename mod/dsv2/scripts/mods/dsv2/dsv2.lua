local mod = get_mod("dsv2")

-- Necromorph Tide: Dead Space 2 models worn by Vermintide 2 enemies.
-- Each player's game hides the enemy's own model and links our skin to its skeleton, so the enemy keeps
-- its AI, animations, hit zones and networking. Nothing new is sent over the network: players without
-- the mod simply see the normal enemies. Which enemy gets which skin comes from dsv2_skins.lua, which is
-- generated from sheets/enemy_skins.json and sheets/props.json.

local SKINS = mod:dofile("scripts/mods/dsv2/dsv2_skins")

local skin_of = {} -- host unit -> our skin unit
local world_of = {} -- host unit -> world it lives in
local queued = {} -- spawned units waiting one frame, so their breed data is set
local warned = {}

local function entry_for(unit, unit_template_name)
	local breed = Unit.get_data(unit, "breed")

	if breed and SKINS.breeds[breed.name] then
		return SKINS.breeds[breed.name]
	end

	return unit_template_name and SKINS.templates[unit_template_name]
end

local function warn_once(key, message, ...)
	if not warned[key] then
		warned[key] = true

		mod:warning(message, ...)
	end
end

local function hide_host(unit, entry)
	Unit.set_unit_visibility(unit, false)

	if entry.hide_inventory then
		local inventory = ScriptUnit.has_extension(unit, "ai_inventory_system")

		if inventory then
			for _, item_unit in ipairs(inventory.inventory_item_units) do
				if Unit.alive(item_unit) then
					Unit.set_unit_visibility(item_unit, false)
				end
			end
		end
	end
end

local function remove_skin(unit)
	local skin = skin_of[unit]

	if skin and Unit.alive(skin) then
		World.destroy_unit(world_of[unit], skin)
	end

	skin_of[unit] = nil
	world_of[unit] = nil
end

local function apply_skin(world, unit, entry)
	if skin_of[unit] or not mod:get(entry.setting) then
		return
	end

	if #entry.links == 0 then
		warn_once(entry.id, "%s has no bone list yet (sheets/enemy_skins.json bones_file); left unskinned", entry.id)

		return
	end

	if not Application.can_get("unit", entry.skin_unit) then
		warn_once(entry.id, "%s: unit %s is not in the mod bundle; left unskinned", entry.id, entry.skin_unit)

		return
	end

	local skin = World.spawn_unit(world, entry.skin_unit, Unit.world_position(unit, 0), Unit.world_rotation(unit, 0))

	for _, link in ipairs(entry.links) do
		local host_node, skin_node = link[1], link[2]

		if type(host_node) == "string" then
			host_node = Unit.has_node(unit, host_node) and Unit.node(unit, host_node)
		end

		if type(skin_node) == "string" then
			skin_node = Unit.has_node(skin, skin_node) and Unit.node(skin, skin_node)
		end

		if host_node and skin_node then
			World.link_unit(world, skin, skin_node, unit, host_node)
		else
			warn_once(entry.id .. tostring(link[1]), "%s: bone %s missing on host or skin", entry.id, tostring(link[1]))
		end
	end

	if entry.scale ~= 1 then
		Unit.set_local_scale(skin, 0, Vector3(entry.scale, entry.scale, entry.scale))
	end

	skin_of[unit] = skin
	world_of[unit] = world

	hide_host(unit, entry)
	Managers.state.unit_spawner:add_destroy_listener(unit, "dsv2_skin", remove_skin)
end

-- Every enemy (spawned here or received as a husk from the host) and every placed banner passes here.
mod:hook_safe(UnitSpawner, "create_unit_extensions", function (self, world, unit, unit_template_name)
	queued[#queued + 1] = {
		world = world,
		unit = unit,
		unit_template_name = unit_template_name,
	}
end)

-- Pooled enemies are made visible again when the game reuses them; keep the original model hidden.
mod:hook_safe(BreedFreezer, "unfreeze_unit", function (self, unit, breed_name)
	if skin_of[unit] then
		hide_host(unit, SKINS.breeds[breed_name] or entry_for(unit))
	end
end)

mod.update = function ()
	if #queued == 0 then
		return
	end

	local pending = queued

	queued = {}

	for _, item in ipairs(pending) do
		local unit = item.unit

		if Unit.alive(unit) then
			local entry = entry_for(unit, item.unit_template_name)

			if entry then
				apply_skin(item.world, unit, entry)
			end
		end
	end
end

-- Leaving a level destroys its world and every skin with it; forget them.
mod.on_game_state_changed = function (status, state_name)
	skin_of = {}
	world_of = {}
	queued = {}
end
