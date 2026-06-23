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
- **Remembers your setup**: once you've used a game directory / world, both the CLI and
  GUI default to them next time, so day-to-day use is just `bedrock-mod-loader install thing.mcpack`.
- **A graphical app** (`bedrock-mod-loader gui`) with Install / Library / Watch Folder /
  Doctor tabs, dark mode, and live progress — for when you don't want a terminal.
- **Manage what's installed**: `info` (preview before installing), `uninstall`,
  `enable`/`disable` per world, and a full pack `list-packs` browser, all without
  touching the in-game UI.
- **Loadouts**: export everything a world has enabled to a single JSON file
  (`export-loadout`) and hand it to a friend, who can `apply-loadout` it to enable the
  same packs in their own world (it tells them exactly what's still missing).
- **`doctor`**: a health check for your install — broken manifests, packs installed in
  two places, worlds referencing packs that no longer exist, permission problems.
- **Self-healing world configs**: every time a world's pack list is written, the
  previous version is kept as a `.bak` file, so a bad edit is always one restore away.

## Install

```sh
pip install -e .
```

This provides the `bedrock-mod-loader` command (also runnable as
`python -m bedrock_mod_loader`). For the graphical app, also install the `gui` extra
to get a modern theme (it works without this too, just with a plainer look):

```sh
pip install -e ".[gui]"
```

## Usage

Install a pack, addon, or world save:

```sh
bedrock-mod-loader install MyAddon.mcaddon --world "My Survival World"
```

Run it again later without `--game-dir`/`--world` and it remembers what you used last time.

Watch a folder and auto-load everything dropped into it:

```sh
bedrock-mod-loader watch ~/Downloads/bedrock-drop --world "My Survival World"
```

Launch the graphical app instead of the terminal:

```sh
bedrock-mod-loader gui
```

Other commands:

```sh
bedrock-mod-loader list-installs            # show detected com.mojang directories
bedrock-mod-loader list-worlds              # list worlds under a game directory
bedrock-mod-loader list-packs               # list packs currently installed
bedrock-mod-loader info MyAddon.mcaddon     # preview a source's contents without installing it
bedrock-mod-loader uninstall "Cool Pack"    # remove a pack from disk + any world enabling it
bedrock-mod-loader enable "Cool Pack" --world "My World"   # enable an already-installed pack
bedrock-mod-loader disable "Cool Pack" --world "My World"  # disable it (files stay on disk)
bedrock-mod-loader doctor                   # health-check your install
bedrock-mod-loader export-loadout my.json --world "My World"   # snapshot a world's enabled packs
bedrock-mod-loader apply-loadout my.json --world "Their World" # recreate that setup elsewhere
```

`uninstall`/`enable`/`disable` accept either a pack's UUID (or a unique prefix of it)
or a name substring; if more than one installed pack matches, you'll be asked to be
more specific.

Useful flags on `install` / `watch`:

| Flag          | Effect                                                                 |
|---------------|-------------------------------------------------------------------------|
| `--game-dir`  | Explicit path to `com.mojang` (skips auto-detection/remembered value)  |
| `--world`     | World (folder or display name) to auto-enable installed packs in       |
| `--prod`      | Install into `behavior_packs`/`resource_packs` instead of `development_*` |
| `--no-enable` | Install without touching any world's pack list                        |
| `--force`     | Reinstall even if an equal or newer version is already present         |

## The GUI

`bedrock-mod-loader gui` opens a desktop app with four tabs:

- **Install** — drop in a pack/addon/world, pick a world from a dropdown, and watch
  install progress live.
- **Library** — every installed pack in one table; enable/disable per world, uninstall,
  or export/apply a loadout.
- **Watch Folder** — the GUI equivalent of `watch`, with a Start/Stop button instead of
  Ctrl+C.
- **Doctor** — run the same health check as the CLI, color-coded.

It needs Tkinter, which ships with most Python installs (on Linux you may need
`sudo apt install python3-tk` if you see an import error). It uses the
[Sun Valley theme](https://github.com/rdbende/sv-ttk) automatically if installed
(`pip install -e ".[gui]"`), and otherwise falls back to a built-in dark theme — no
extra dependency required either way.

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
