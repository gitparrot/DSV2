local mod = get_mod("dsv2")

-- Necromorph Tide: Dead Space 2 models worn by Vermintide 2 enemies, a hero career and its weapon.
-- Each player's game hides the original model and links our skin to its skeleton, so the enemy (or hero) keeps
-- its AI, animations, hit zones and networking. Nothing new is sent over the network: players without the mod
-- simply see the normal models. Which unit gets which skin comes from dsv2_skins.lua, generated from
-- sheets/enemy_skins.json, props.json, player_skins.json and weapon_skins.json.

local SKINS = mod:dofile("scripts/mods/dsv2/dsv2_skins")

local skin_of = {} -- host unit -> our skin unit
local world_of = {} -- host unit -> world it lives in
local queued = {} -- spawned units waiting one frame, so their breed data is set
local warned = {}
local skinned_count = {} -- entry id -> skins applied this session (for /dsv2_status)
local wanted = setmetatable({}, { __mode = "k" }) -- unit -> visibility the game last asked for
local weapon_entry_of -- AttachmentNodeLinking table -> weapon skin entry, built on first use
local owner_of = {} -- hero 3rd-person mesh -> its player unit (to keep your own body out of your first-person view)
local fp_hidden = {} -- hero 3rd-person mesh -> true while we hide its skin for the first-person camera
local entry_of = {} -- host unit -> its skin entry
local retarget_of = {} -- host unit -> { pairs = { host node, skin node, ... }, hips_host, hips_skin, factor }

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

-- Call before the skin is registered in skin_of, so the visibility hook below treats this as a plain hide.
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

local function rest_scale(unit, node)
	return Vector3.length(Matrix4x4.x(Unit.world_pose(unit, node)))
end

local function remove_skin(unit)
	local skin = skin_of[unit]

	if skin and Unit.alive(skin) then
		World.destroy_unit(world_of[unit], skin)
	end

	skin_of[unit] = nil
	world_of[unit] = nil
	owner_of[unit] = nil
	fp_hidden[unit] = nil
	retarget_of[unit] = nil
	entry_of[unit] = nil
end

-- Retarget skins have their own skeleton: a copy of the host's (same joint names, parents and rest orientations)
-- with the joints moved to the skin's proportions. Only the root is linked; each frame update_retargets copies the
-- host's local joint rotations onto it, and the hips' position scaled from the host's leg length to the skin's.
local function setup_retarget(unit, skin, entry)
	local rt = entry.retarget
	local node_pairs = {}

	for _, name in ipairs(rt.bones) do
		if Unit.has_node(unit, name) and Unit.has_node(skin, name) then
			node_pairs[#node_pairs + 1] = Unit.node(unit, name)
			node_pairs[#node_pairs + 1] = Unit.node(skin, name)
		else
			warn_once(entry.id .. name, "%s: joint %s missing on host or skin", entry.id, name)
		end
	end

	local hips_host = Unit.has_node(unit, rt.hips) and Unit.node(unit, rt.hips)
	local hips_skin = Unit.has_node(skin, rt.hips) and Unit.node(skin, rt.hips)
	local h = rt.host_hips_rest
	local host_len = math.sqrt(h[1] * h[1] + h[2] * h[2] + h[3] * h[3])
	-- The skin's hips rest offset is in its own parent's units (which may carry the SDK's x100), so this ratio
	-- converts both the size difference and the units.
	local factor = hips_skin and host_len > 0 and Vector3.length(Unit.local_position(skin, hips_skin)) / host_len

	retarget_of[unit] = {
		pairs = node_pairs,
		hips_host = factor and hips_host,
		hips_skin = factor and hips_skin,
		factor = factor,
	}

	return #node_pairs / 2
end

-- listen: also register a destroy listener (networked enemies and banners; local units like hero meshes and
-- weapons are cleaned up by the sweep in mod.update instead).
local function apply_skin(world, unit, entry, listen)
	if skin_of[unit] or not mod:get(entry.setting) then
		return
	end

	if #entry.links == 0 and not entry.retarget then
		warn_once(entry.id, "%s has no bone list yet (bones_file in the sheets); left unskinned", entry.id)

		return
	end

	if not Application.can_get("unit", entry.skin_unit) then
		warn_once(entry.id, "%s: unit %s is not in the mod bundle; left unskinned", entry.id, entry.skin_unit)

		return
	end

	local skin = World.spawn_unit(world, entry.skin_unit, Unit.world_position(unit, 0), Unit.world_rotation(unit, 0))
	local pairs_to_link = {}
	local links_root = false

	if entry.retarget then
		pairs_to_link[1] = { 0, 0, rest_scale(skin, 0) }
		links_root = true
	end

	for _, link in ipairs(entry.links) do
		local host_node, skin_node = link[1], link[2]

		if type(host_node) == "string" then
			host_node = Unit.has_node(unit, host_node) and Unit.node(unit, host_node)
		end

		if type(skin_node) == "string" then
			skin_node = Unit.has_node(skin, skin_node) and Unit.node(skin, skin_node)
		end

		if host_node and skin_node then
			-- Read the rest scale before linking: linking replaces the bone's local pose with identity.
			pairs_to_link[#pairs_to_link + 1] = { host_node, skin_node, rest_scale(skin, skin_node) }
			links_root = links_root or skin_node == 0
		else
			warn_once(entry.id .. tostring(link[1]), "%s: bone %s missing on host or skin", entry.id, tostring(link[1]))
		end
	end

	-- The skin's root follows the host's root, so the engine culls the skin where the host is, not at its spawn point.
	if not links_root then
		World.link_unit(world, skin, 0, unit, 0)
	end

	local scale_fixed = 0

	for _, p in ipairs(pairs_to_link) do
		local host_node, skin_node, scale = p[1], p[2], p[3]

		World.link_unit(world, skin, skin_node, unit, host_node)

		-- The SDK's FBX import stores the vertices at 1/100 and puts x100 on the skeleton's rest pose. Linking drops that
		-- x100, which would draw the skin at 1/100 size, so put it back on each linked bone.
		if math.abs(scale - 1) > 0.001 then
			Unit.set_local_scale(skin, skin_node, Vector3(scale, scale, scale))
			scale_fixed = scale_fixed + 1
		end
	end

	skinned_count[entry.id] = (skinned_count[entry.id] or 0) + 1

	if skinned_count[entry.id] == 1 then
		mod:info("%s: first skin on %s, %d/%d bones linked, %d rest scales restored", entry.id, entry.skin_unit,
			#pairs_to_link, #entry.links, scale_fixed)
	end

	if entry.retarget then
		local joints = setup_retarget(unit, skin, entry)

		if skinned_count[entry.id] == 1 then
			mod:info("%s: retargeting %d/%d joints, hips factor %s", entry.id, joints, #entry.retarget.bones,
				tostring(retarget_of[unit].factor))
		end
	end

	if entry.scale ~= 1 then
		Unit.set_local_scale(skin, 0, Vector3(entry.scale, entry.scale, entry.scale))
	end

	-- Start as visible as the game currently wants the host (e.g. your own 3rd-person body while in first person).
	local was_wanted = wanted[unit]

	hide_host(unit, entry)

	wanted[unit] = was_wanted
	skin_of[unit] = skin
	world_of[unit] = world
	entry_of[unit] = entry

	if was_wanted == false then
		Unit.set_unit_visibility(skin, false)
	end

	if listen then
		Managers.state.unit_spawner:add_destroy_listener(unit, "dsv2_skin", remove_skin)
	end
end

-- The game shows and hides units through here (first/third person switches, hidden weapons, frozen enemies).
-- A host wearing a skin stays hidden and the skin gets the visibility the game asked for.
mod:hook(Unit, "set_unit_visibility", function (func, unit, visible, ...)
	wanted[unit] = visible

	local skin = skin_of[unit]

	if skin then
		if Unit.alive(skin) then
			func(skin, visible and not fp_hidden[unit], ...)
		end

		return func(unit, false, ...)
	end

	return func(unit, visible, ...)
end)

-- Every enemy (spawned here or received as a husk from the host) and every placed banner passes here.
mod:hook_safe(UnitSpawner, "create_unit_extensions", function (self, world, unit, unit_template_name)
	queued[#queued + 1] = {
		world = world,
		unit = unit,
		unit_template_name = unit_template_name,
	}
end)

-- Pooled enemies come back through here, not through create_unit_extensions. The game's "show" on reuse goes
-- through the visibility hook (host stays hidden, skin shows); a pooled enemy that never had a skin gets one.
mod:hook_safe(BreedFreezer, "unfreeze_unit", function (self, unit, breed_name)
	local entry = SKINS.breeds[breed_name] or entry_for(unit)

	if entry and not skin_of[unit] then
		apply_skin(self.world, unit, entry, true)
	end
end)

-- Every hero's third-person body (yours and other players') is spawned here; the career picks the skin.
mod:hook_safe(PlayerUnitCosmeticExtension, "_init_mesh_attachment", function (self, world, unit, skin_name, profile, career)
	local entry = career and SKINS.careers[career.name] and SKINS.careers[career.name].third_person

	if entry and self._tp_unit_mesh then
		apply_skin(world, self._tp_unit_mesh, entry)

		if skin_of[self._tp_unit_mesh] then
			owner_of[self._tp_unit_mesh] = unit
		end
	end
end)

-- Your first-person arms are spawned here. The career is looked up the same way the game does it.
mod:hook_safe(PlayerUnitFirstPerson, "init", function (self, extension_init_context, unit, extension_init_data)
	local profile = extension_init_data.profile
	local hero_attributes = Managers.backend:get_interface("hero_attributes")
	local career = profile and profile.careers[hero_attributes:get(profile.display_name, "career") or 1]
	local entry = career and SKINS.careers[career.name] and SKINS.careers[career.name].first_person

	if entry and self.first_person_attachment_unit then
		apply_skin(self.world, self.first_person_attachment_unit, entry)
	end
end)

-- Weapons are linked to hands and holsters here. The linking table the game passes identifies the weapon:
-- AttachmentNodeLinking.<key>.<first_person|third_person>, or its wielded/unwielded sub-tables.
local function weapon_entry(node_linking)
	if not weapon_entry_of then
		weapon_entry_of = {}

		for key, views in pairs(SKINS.weapons) do
			local linking = AttachmentNodeLinking[key]

			for view, entry in pairs(views) do
				local sub = linking and linking[view]

				if type(sub) == "table" then
					weapon_entry_of[sub] = entry

					for _, part in pairs(sub) do
						if type(part) == "table" then
							weapon_entry_of[part] = entry
						end
					end
				end
			end
		end
	end

	return weapon_entry_of[node_linking]
end

mod:hook_safe(AttachmentUtils, "link", function (world, source, target, node_linking)
	local entry = node_linking and weapon_entry(node_linking)

	if entry and Unit.alive(target) then
		apply_skin(world, target, entry)
	end
end)

-- Shot effects (weapon_skins muzzle_effect / trail_effect). Each crank gun shot sets hit_position and fires
-- lua_bullet_trail on the gun, whose flow draws the muzzle flash and tracer. The action keeps its own local copy of
-- Unit.flow_event, so the hook goes on the action's method: a skinned gun with shot_fx draws its own effects
-- from the gun's fx_muzzle node instead. Effects that aren't loaded fall back to the game's.
local function can_spawn(entry, name)
	if Application.can_get("particles", name) then
		return true
	end

	warn_once(entry.id .. name, "%s: effect %s is not loaded; using the game's own", entry.id, name)

	return false
end

local function spawn_shot_fx(weapon, end_position)
	local entry = skin_of[weapon] and entry_of[weapon]
	local fx = entry and entry.shot_fx
	local world = world_of[weapon]

	if not (fx and world and Unit.alive(weapon)) then
		return false
	end

	if (fx.muzzle and not can_spawn(entry, fx.muzzle)) or (fx.trail and not can_spawn(entry, fx.trail)) then
		return false
	end

	local start = Unit.world_position(weapon, Unit.has_node(weapon, "fx_muzzle") and Unit.node(weapon, "fx_muzzle") or 0)
	local to_hit = end_position - start
	local distance = Vector3.length(to_hit)
	local rotation = distance > 0.001 and Quaternion.look(to_hit, Vector3.up()) or Unit.world_rotation(weapon, 0)

	if fx.muzzle then
		World.create_particles(world, fx.muzzle, start, rotation)
	end

	if fx.trail then
		local id = World.create_particles(world, fx.trail, start, rotation)

		if fx.trail_variable then
			local variable = World.find_particles_variable(world, fx.trail, fx.trail_variable)

			World.set_particles_variable(world, id, variable, Vector3(0.3, distance, 0))
		end
	end

	return true
end

mod:hook(ActionCareerDREngineer, "_add_bullet_trail", function (func, self, end_position, lifetime)
	if self.is_bot or not spawn_shot_fx(self.weapon_unit, end_position) then
		return func(self, end_position, lifetime)
	end
end)

mod:command("dsv2_status", "Necromorph Tide: how many units wear a skin right now", function ()
	local alive = 0

	for _, skin in pairs(skin_of) do
		if Unit.alive(skin) then
			alive = alive + 1
		end
	end

	local parts = {}

	for id, n in pairs(skinned_count) do
		parts[#parts + 1] = string.format("%s %d", id, n)
	end

	table.sort(parts)
	mod:echo("dsv2: %d skins alive; applied this session: %s", alive, #parts > 0 and table.concat(parts, ", ") or "none")
end)

-- Your own 3rd-person body is never hidden through set_unit_visibility: in first person the game keeps it out of
-- view by other means (it starts "visible" and first-person mode never toggles it). Isaac would then fill the
-- camera, so hide your own skin whenever your first-person view is active.
local function update_own_body()
	for mesh, owner in pairs(owner_of) do
		local skin = skin_of[mesh]
		local fp = Unit.alive(owner) and ScriptUnit.has_extension(owner, "first_person_system")

		if skin and fp and Unit.alive(skin) then
			local hide = fp:first_person_mode_active()

			if hide ~= (fp_hidden[mesh] or false) then
				fp_hidden[mesh] = hide

				Unit.set_unit_visibility(skin, not hide and wanted[mesh] ~= false)
			end
		end
	end
end

local function update_retargets()
	for unit, rt in pairs(retarget_of) do
		local skin = skin_of[unit]

		if skin and Unit.alive(skin) and Unit.alive(unit) and not fp_hidden[unit] then
			local p = rt.pairs

			for i = 1, #p, 2 do
				Unit.set_local_rotation(skin, p[i + 1], Unit.local_rotation(unit, p[i]))
			end

			if rt.factor then
				Unit.set_local_position(skin, rt.hips_skin, Unit.local_position(unit, rt.hips_host) * rt.factor)
			end
		end
	end
end

mod.update = function ()
	-- Hero meshes and weapons are local units with no destroy listener: drop skins whose host is gone.
	for unit in pairs(skin_of) do
		if not Unit.alive(unit) then
			remove_skin(unit)
		end
	end

	update_own_body()
	update_retargets()

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
				apply_skin(item.world, unit, entry, true)
			end
		end
	end
end

-- Leaving a level destroys its world and every skin with it; forget them.
mod.on_game_state_changed = function (status, state_name)
	skin_of = {}
	world_of = {}
	queued = {}
	owner_of = {}
	fp_hidden = {}
	retarget_of = {}
	entry_of = {}
end
