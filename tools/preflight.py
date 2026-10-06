"""Preflight: lay every sheet over each other and list what is unfilled, unverified or unresolved.

Run from the repo root:  python tools/preflight.py
Exit code 0 only when every cell is filled and checked and every reference resolves.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEETS = ["source_models", "enemy_skins", "props", "player_skins", "weapon_skins", "settings", "hooks"]
SKIN_SHEETS = ("enemy_skins", "props", "player_skins", "weapon_skins")
UNFILLED = ("TODO_PC", None, "")
STATUS_COLUMNS = ("extracted", "rigged", "tested_in_game")
MOD_SCRIPT = os.path.join(ROOT, "mod", "dsv2", "scripts", "mods", "dsv2", "dsv2.lua")


def load(name):
    with open(os.path.join(ROOT, "sheets", name + ".json"), encoding="utf-8") as f:
        return json.load(f)


def preflight():
    sheets = {name: load(name) for name in SHEETS}
    unfilled, unverified, broken = [], [], []

    for name, sheet in sheets.items():
        columns = sheet["columns"]
        for row in sheet["rows"]:
            where = f"{name}[{row.get('id')}]"
            for column in columns:
                if column not in row:
                    unfilled.append(f"{where}.{column}: missing")
                elif row[column] in UNFILLED:
                    unfilled.append(f"{where}.{column}: {row[column]!r}")
                elif column in STATUS_COLUMNS and row[column] is not True:
                    unverified.append(f"{where}.{column}")
            for column in row:
                if column not in columns:
                    broken.append(f"{where}.{column}: column not declared in sheet")

    ids = {name: {row["id"] for row in sheet["rows"]} for name, sheet in sheets.items()}
    for name in SKIN_SHEETS:
        for row in sheets[name]["rows"]:
            where = f"{name}[{row['id']}]"
            if row["source_model"] not in ids["source_models"]:
                broken.append(f"{where}.source_model -> source_models: {row['source_model']!r} not found")
            if row["setting"] not in ids["settings"]:
                broken.append(f"{where}.setting -> settings: {row['setting']!r} not found")

    seen_breeds = {}
    for row in sheets["enemy_skins"]["rows"]:
        if row["breed"] in seen_breeds:
            broken.append(f"enemy_skins[{row['id']}].breed {row['breed']!r} already skinned by {seen_breeds[row['breed']]}")
        seen_breeds[row["breed"]] = row["id"]
        bones = os.path.join(ROOT, row["bones_file"])
        if not os.path.isfile(bones) or not read_bones(bones):
            unfilled.append(f"enemy_skins[{row['id']}].bones_file: {row['bones_file']} missing or empty (export from the SDK)")

    for row in sheets["player_skins"]["rows"]:
        bones = os.path.join(ROOT, row["bones_file"])
        if not os.path.isfile(bones) or not read_bones(bones):
            unfilled.append(f"player_skins[{row['id']}].bones_file: {row['bones_file']} missing or empty")
        if row["view"] not in ("first_person", "third_person"):
            broken.append(f"player_skins[{row['id']}].view: {row['view']!r} is not first_person/third_person")
    for row in sheets["weapon_skins"]["rows"]:
        if row["view"] not in ("first_person", "third_person"):
            broken.append(f"weapon_skins[{row['id']}].view: {row['view']!r} is not first_person/third_person")

    used = {row["source_model"] for name in SKIN_SHEETS for row in sheets[name]["rows"]}
    for model in sorted(ids["source_models"] - used):
        broken.append(f"source_models[{model}]: not used by any skin or prop")

    if os.path.isfile(MOD_SCRIPT):
        with open(MOD_SCRIPT, encoding="utf-8") as f:
            script = f.read()
        for row in sheets["hooks"]["rows"]:
            cls, _, func = row["target"].partition(".")
            if row["kind"] == "update":
                needle = "mod.update"
            elif row["kind"] == "listener":
                needle = func
            elif row["kind"] == "hook":
                needle = f'mod:hook({cls}, "{func}"'
            else:
                needle = f'mod:hook_safe({cls}, "{func}"'
            if needle not in script:
                broken.append(f"hooks[{row['id']}]: {row['target']} not found in dsv2.lua")
    else:
        broken.append("mod/dsv2/scripts/mods/dsv2/dsv2.lua: missing")

    return unfilled, unverified, broken


def read_bones(path):
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


def main():
    unfilled, unverified, broken = preflight()
    for title, items in (("Unfilled cells", unfilled), ("Unverified (not yet checked on PC / in game)", unverified),
                         ("Broken references", broken)):
        print(f"{title}: {len(items)}")
        for item in items:
            print("  - " + item)
    clean = not (unfilled or unverified or broken)
    print("PREFLIGHT CLEAN" if clean else "PREFLIGHT NOT CLEAN: fix the items above before building")
    return 0 if clean else 1


if __name__ == "__main__":
    sys.exit(main())
