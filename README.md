# bedrock-mod-loader

A Minecraft Bedrock multi-tool whose main job is to **automatically load mod packs
and resources**: point it at a behavior pack, resource pack, addon, or world save and
it figures out what it is, copies it into the right `com.mojang` folder, and (if you
give it a world) enables it there too — no manual "Settings > Resource Packs" clicking.

## Features

- **Auto-detects pack type** from `manifest.json` — behavior pack, resource pack, or
  skin pack — no need to tell it what you're installing.
- **Unpacks anything**: raw pack folders, `.mcpack`, `.mcaddon` (including ones with
  multiple sub-packs or nested `.mcpack` files), `.mcworld` saves, and plain `.zip`.
- **Auto-enables packs in a world** by writing `world_behavior_packs.json` /
  `world_resource_packs.json`, so the pack is active the moment you load the world.
- **Version-aware installs**: re-running install on a newer version upgrades the pack
  in place; an older or identical version is skipped (unless `--force`).
- **`watch` mode**: point it at a "drop folder" and it installs (and enables) every
  pack you drag into it, automatically, for as long as it runs.
- **Auto-detects your Minecraft install** (`com.mojang`) on Windows out of the box; on
  Linux/macOS or custom setups, point it at one with `--game-dir` or `BEDROCK_GAME_DIR`.

## Install

```sh
pip install -e .
```

This provides the `bedrock-mod-loader` command (also runnable as
`python -m bedrock_mod_loader`).

## Usage

Install a pack, addon, or world save:

```sh
bedrock-mod-loader install MyAddon.mcaddon --world "My Survival World"
```

Watch a folder and auto-load everything dropped into it:

```sh
bedrock-mod-loader watch ~/Downloads/bedrock-drop --world "My Survival World"
```

Other commands:

```sh
bedrock-mod-loader list-installs   # show detected com.mojang directories
bedrock-mod-loader list-worlds     # list worlds under a game directory
bedrock-mod-loader list-packs      # list packs currently installed
```

Useful flags on `install` / `watch`:

| Flag          | Effect                                                                 |
|---------------|-------------------------------------------------------------------------|
| `--game-dir`  | Explicit path to `com.mojang` (skips auto-detection)                   |
| `--world`     | World (folder or display name) to auto-enable installed packs in       |
| `--prod`      | Install into `behavior_packs`/`resource_packs` instead of `development_*` |
| `--no-enable` | Install without touching any world's pack list                        |
| `--force`     | Reinstall even if an equal or newer version is already present         |

## How "auto-load" works

Copying a pack into `development_behavior_packs` makes it *available*, but Minecraft
only actually loads it into a world once that world's `world_behavior_packs.json` /
`world_resource_packs.json` lists the pack's UUID and version. `bedrock-mod-loader`
writes those files for you, which is what makes loading genuinely automatic instead of
"copy the files, then go flip switches in the in-game UI."

## Supported pack sources

- A folder containing `manifest.json` (a raw dev pack)
- A folder of sub-packs, e.g. an addon with `BP/` and `RP/` subfolders
- `.mcpack` — a zipped single pack
- `.mcaddon` — a zipped bundle of packs (folders or nested `.mcpack` files)
- `.mcworld` — a zipped world save, installed into `minecraftWorlds`
- Plain `.zip` containing any of the above

## Development

```sh
pip install -e ".[dev]"
pytest
```
