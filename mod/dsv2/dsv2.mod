return {
	run = function()
		fassert(rawget(_G, "new_mod"), "`dsv2` mod must be lower than Vermintide Mod Framework in your launcher's load order.")

		new_mod("dsv2", {
			mod_script       = "scripts/mods/dsv2/dsv2",
			mod_data         = "scripts/mods/dsv2/dsv2_data",
			mod_localization = "scripts/mods/dsv2/dsv2_localization",
		})
	end,
	packages = {
		"resource_packages/dsv2/dsv2",
	},
}
