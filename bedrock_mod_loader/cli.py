"""Command line interface for bedrock-mod-loader."""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Optional

from . import config, discovery, doctor, installer, loadout, world_config
from .packs import PackError, discover_sources, is_world_save, read_pack_info


def _try_resolve_game_dir(args) -> Optional[Path]:
    if args.game_dir:
        return Path(args.game_dir)
    found = discovery.find_game_dirs()
    if found:
        return found[0]
    remembered = config.load_config().get("game_dir")
    if remembered and Path(remembered).is_dir():
        return Path(remembered)
    return None


def resolve_game_dir(args) -> Path:
    game_dir = _try_resolve_game_dir(args)
    if game_dir is None:
        raise SystemExit(
            "Could not auto-detect a Minecraft Bedrock game directory (com.mojang).\n"
            "Pass --game-dir explicitly, or set the BEDROCK_GAME_DIR environment variable."
        )
    game_dir.mkdir(parents=True, exist_ok=True)
    config.update_config(game_dir=str(game_dir))
    return game_dir


def _resolve_world_name(args) -> Optional[str]:
    world = getattr(args, "world", None)
    if world:
        return world
    return config.load_config().get("last_world")


def _require_world(args, game_dir: Path) -> Path:
    world_name = _resolve_world_name(args)
    if not world_name:
        raise SystemExit("Specify --world (or run `install --world <name>` once to remember it).")
    world_dir = discovery.find_world_by_name(game_dir, world_name)
    if world_dir is None:
        raise SystemExit(f"World '{world_name}' not found under {game_dir}")
    config.update_config(last_world=world_dir.name)
    return world_dir


def _format_version(version) -> str:
    return ".".join(str(part) for part in version)


def _warn_missing_dependencies(info, game_dir: Path, log=print) -> None:
    if not info.dependencies:
        return
    installed_uuids = {p.uuid for p in installer.iter_installed_packs(game_dir)}
    installed_uuids.add(info.uuid)
    for dep_uuid, dep_version in info.dependencies:
        if dep_uuid not in installed_uuids:
            suffix = f" v{_format_version(dep_version)}" if dep_version else ""
            log(f"    warning: depends on {dep_uuid}{suffix}, which isn't installed")


def _install_one(source: Path, game_dir: Path, scratch: Path, dev: bool, force: bool, world_dir, enable: bool, log=print) -> None:
    """Install everything discoverable under `source`. Shared by the CLI and the GUI
    (which passes a `log` callback that writes into a text widget instead of stdout).
    """
    for found in discover_sources(source, scratch):
        if is_world_save(found):
            dest = installer.install_world(found, game_dir, force=force)
            log(f"[world] installed '{found.name}' -> {dest}")
            continue

        info = read_pack_info(found)
        result = installer.install_pack(info, game_dir, dev=dev, force=force)
        log(f"[{result.kind}] {result.name} v{_format_version(result.version)}: {result.action} -> {result.installed_path}")

        if result.action.startswith(("installed", "updated")):
            _warn_missing_dependencies(info, game_dir, log=log)

        if enable and world_dir is not None and result.action.startswith(("installed", "updated")):
            changed = world_config.enable_pack_in_world(world_dir, result.kind, result.uuid, result.version)
            if changed:
                log(f"    enabled in world '{world_dir.name}'")


def cmd_install(args) -> None:
    game_dir = resolve_game_dir(args)
    world_name = _resolve_world_name(args)
    world_dir = None
    if world_name:
        world_dir = discovery.find_world_by_name(game_dir, world_name)
        if world_dir is None:
            print(f"warning: world '{world_name}' not found under {game_dir}; packs will install but won't be enabled.")
        else:
            if not args.world:
                print(f"(using remembered world '{world_name}'; pass --world to override)")
            config.update_config(last_world=world_dir.name)

    scratch = Path(tempfile.mkdtemp(prefix="bedrock-mod-loader-"))
    try:
        for source in args.sources:
            _install_one(Path(source), game_dir, scratch, dev=not args.prod, force=args.force, world_dir=world_dir, enable=not args.no_enable)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def cmd_watch(args) -> None:
    game_dir = resolve_game_dir(args)
    drop_dir = Path(args.source)
    drop_dir.mkdir(parents=True, exist_ok=True)

    world_name = _resolve_world_name(args)
    world_dir = None
    if world_name:
        world_dir = discovery.find_world_by_name(game_dir, world_name)
        if world_dir is None:
            print(f"warning: world '{world_name}' not found yet; packs will install but won't be enabled until it exists.")
        else:
            if not args.world:
                print(f"(using remembered world '{world_name}'; pass --world to override)")
            config.update_config(last_world=world_dir.name)

    print(f"Watching {drop_dir} -> installing into {game_dir} ({'production' if args.prod else 'development'} packs)")
    if world_dir is not None:
        print(f"New packs will be auto-enabled in world '{world_dir.name}'")
    print("Press Ctrl+C to stop.")

    scratch = Path(tempfile.mkdtemp(prefix="bedrock-mod-loader-watch-"))

    def handle(entry: Path) -> None:
        try:
            _install_one(entry, game_dir, scratch, dev=not args.prod, force=args.force, world_dir=world_dir, enable=not args.no_enable)
        except PackError as exc:
            print(f"  skipped {entry.name}: {exc}")

    from . import watcher

    try:
        watcher.watch_forever(drop_dir, handle, poll_interval=args.interval)
    except KeyboardInterrupt:
        print("\nStopped watching.")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def cmd_list_installs(args) -> None:
    dirs = discovery.find_game_dirs()
    if not dirs:
        print("No Minecraft Bedrock game directories were auto-detected on this system.")
        print("Pass --game-dir explicitly, or set the BEDROCK_GAME_DIR environment variable.")
        return
    for game_dir in dirs:
        print(game_dir)


def cmd_list_worlds(args) -> None:
    game_dir = resolve_game_dir(args)
    worlds = discovery.list_worlds(game_dir)
    if not worlds:
        print(f"No worlds found under {game_dir / 'minecraftWorlds'}")
        return
    for world_dir in worlds:
        levelname_file = world_dir / "levelname.txt"
        label = world_dir.name
        if levelname_file.is_file():
            label = levelname_file.read_text(encoding="utf-8", errors="ignore").strip() or label
        print(f"{world_dir.name}\t{label}")


def cmd_list_packs(args) -> None:
    game_dir = resolve_game_dir(args)
    found_any = False
    for info in installer.iter_installed_packs(game_dir):
        found_any = True
        print(f"[{info.kind}] {info.name}  uuid={info.uuid}  v{_format_version(info.version)}")
        if info.description:
            print(f"    {info.description}")
    if not found_any:
        print(f"No installed packs found under {game_dir}")


def cmd_info(args) -> None:
    scratch = Path(tempfile.mkdtemp(prefix="bedrock-mod-loader-info-"))
    try:
        found_any = False
        for found in discover_sources(Path(args.source), scratch):
            found_any = True
            if is_world_save(found):
                print(f"[world] {installer.world_display_name(found)}")
                continue
            info = read_pack_info(found)
            print(f"[{info.kind}] {info.name} v{_format_version(info.version)}")
            print(f"    uuid: {info.uuid}")
            if info.description:
                print(f"    description: {info.description}")
            if info.min_engine_version:
                print(f"    min_engine_version: {_format_version(info.min_engine_version)}")
            if info.dependencies:
                print("    dependencies:")
                for dep_uuid, dep_version in info.dependencies:
                    suffix = f" v{_format_version(dep_version)}" if dep_version else ""
                    print(f"      - {dep_uuid}{suffix}")
        if not found_any:
            print("No installable content found at that source.")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def cmd_uninstall(args) -> None:
    game_dir = resolve_game_dir(args)
    info = installer.find_installed_pack(game_dir, args.identifier)
    disabled_in = []
    for world_dir in discovery.list_worlds(game_dir):
        if world_config.disable_pack_in_world(world_dir, info.kind, info.uuid):
            disabled_in.append(world_dir.name)
    installer.uninstall_pack(info)
    print(f"Removed [{info.kind}] {info.name} v{_format_version(info.version)} ({info.path})")
    if disabled_in:
        print(f"  disabled in world(s): {', '.join(disabled_in)}")


def cmd_enable(args) -> None:
    game_dir = resolve_game_dir(args)
    world_dir = _require_world(args, game_dir)
    info = installer.find_installed_pack(game_dir, args.identifier)
    changed = world_config.enable_pack_in_world(world_dir, info.kind, info.uuid, info.version)
    print(f"{'Enabled' if changed else 'Already enabled'}: [{info.kind}] {info.name} in world '{world_dir.name}'")


def cmd_disable(args) -> None:
    game_dir = resolve_game_dir(args)
    world_dir = _require_world(args, game_dir)
    info = installer.find_installed_pack(game_dir, args.identifier)
    changed = world_config.disable_pack_in_world(world_dir, info.kind, info.uuid)
    print(f"{'Disabled' if changed else 'Was not enabled'}: [{info.kind}] {info.name} in world '{world_dir.name}'")


def cmd_doctor(args) -> None:
    game_dir = _try_resolve_game_dir(args)
    results = doctor.run_diagnostics(game_dir)
    labels = {doctor.OK: "[ok]   ", doctor.WARN: "[warn] ", doctor.ERROR: "[error]"}
    for result in results:
        print(f"{labels.get(result.level, '[?]')} {result.message}")
    if any(result.level == doctor.ERROR for result in results):
        raise SystemExit(1)


def cmd_export_loadout(args) -> None:
    game_dir = resolve_game_dir(args)
    world_dir = _require_world(args, game_dir)
    installed_by_uuid = {p.uuid: p for p in installer.iter_installed_packs(game_dir)}
    data = loadout.build_loadout(world_dir, installed_by_uuid)
    dest = Path(args.output)
    loadout.write_loadout(data, dest)
    print(f"Exported {len(data['packs'])} pack(s) from world '{world_dir.name}' -> {dest}")


def cmd_apply_loadout(args) -> None:
    game_dir = resolve_game_dir(args)
    world_dir = _require_world(args, game_dir)
    data = loadout.read_loadout(Path(args.loadout_file))
    installed_by_uuid = {p.uuid: p for p in installer.iter_installed_packs(game_dir)}
    result = loadout.apply_loadout(data, world_dir, installed_by_uuid)
    for entry in result.applied:
        print(f"  enabled [{entry.kind}] {entry.name or entry.uuid}")
    for entry in result.missing:
        label = entry.name or entry.uuid
        print(f"  missing: [{entry.kind}] {label} ({entry.uuid}) -- install it, then re-run apply-loadout")
    print(f"Applied {len(result.applied)} pack(s) to world '{world_dir.name}'; {len(result.missing)} missing.")


def cmd_gui(args) -> None:
    try:
        from . import gui
    except ImportError as exc:
        raise SystemExit(
            "The GUI needs Tkinter, which isn't available in this Python install.\n"
            "On Linux, install it with your package manager (e.g. `sudo apt install python3-tk`); "
            "on Windows/macOS the python.org installer already includes it.\n"
            f"({exc})"
        )
    gui.launch(game_dir=Path(args.game_dir) if args.game_dir else None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bedrock-mod-loader", description="Install and auto-load Minecraft Bedrock mod packs and resources.")
    sub = parser.add_subparsers(dest="command", required=True)

    install_p = sub.add_parser("install", help="Install one or more packs, addons, or world saves.")
    install_p.add_argument("sources", nargs="+", help="Path(s) to a pack folder, .mcpack, .mcaddon, .mcworld, or .zip file.")
    install_p.add_argument("--game-dir", help="Path to the com.mojang directory (auto-detected if omitted).")
    install_p.add_argument("--world", help="World name (folder or display name) to auto-enable installed packs in. Remembered for next time.")
    install_p.add_argument("--prod", action="store_true", help="Install into behavior_packs/resource_packs instead of development_*.")
    install_p.add_argument("--no-enable", action="store_true", help="Install without enabling in the target world.")
    install_p.add_argument("--force", action="store_true", help="Overwrite even if an equal or newer version is already installed.")
    install_p.set_defaults(func=cmd_install)

    watch_p = sub.add_parser("watch", help="Watch a folder and auto-install/enable any pack dropped into it.")
    watch_p.add_argument("source", help="Folder to watch for new packs.")
    watch_p.add_argument("--game-dir", help="Path to the com.mojang directory (auto-detected if omitted).")
    watch_p.add_argument("--world", help="World name (folder or display name) to auto-enable installed packs in. Remembered for next time.")
    watch_p.add_argument("--prod", action="store_true", help="Install into behavior_packs/resource_packs instead of development_*.")
    watch_p.add_argument("--no-enable", action="store_true", help="Install without enabling in the target world.")
    watch_p.add_argument("--force", action="store_true", help="Overwrite even if an equal or newer version is already installed.")
    watch_p.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds (default: 2.0).")
    watch_p.set_defaults(func=cmd_watch)

    list_installs_p = sub.add_parser("list-installs", help="Show auto-detected Minecraft Bedrock game directories.")
    list_installs_p.set_defaults(func=cmd_list_installs)

    list_worlds_p = sub.add_parser("list-worlds", help="List worlds available under a game directory.")
    list_worlds_p.add_argument("--game-dir")
    list_worlds_p.set_defaults(func=cmd_list_worlds)

    list_packs_p = sub.add_parser("list-packs", help="List packs currently installed under a game directory.")
    list_packs_p.add_argument("--game-dir")
    list_packs_p.set_defaults(func=cmd_list_packs)

    info_p = sub.add_parser("info", help="Preview a pack/addon/world source's details without installing it.")
    info_p.add_argument("source", help="Path to a pack folder, .mcpack, .mcaddon, .mcworld, or .zip file.")
    info_p.set_defaults(func=cmd_info)

    uninstall_p = sub.add_parser("uninstall", help="Remove an installed pack from disk and from any world that enables it.")
    uninstall_p.add_argument("identifier", help="Installed pack's UUID (or prefix) or name.")
    uninstall_p.add_argument("--game-dir")
    uninstall_p.set_defaults(func=cmd_uninstall)

    enable_p = sub.add_parser("enable", help="Enable an already-installed pack in a world, without reinstalling.")
    enable_p.add_argument("identifier", help="Installed pack's UUID (or prefix) or name.")
    enable_p.add_argument("--world", help="World name. Remembered for next time.")
    enable_p.add_argument("--game-dir")
    enable_p.set_defaults(func=cmd_enable)

    disable_p = sub.add_parser("disable", help="Disable a pack in a world (its files stay installed).")
    disable_p.add_argument("identifier", help="Installed pack's UUID (or prefix) or name.")
    disable_p.add_argument("--world", help="World name. Remembered for next time.")
    disable_p.add_argument("--game-dir")
    disable_p.set_defaults(func=cmd_disable)

    doctor_p = sub.add_parser("doctor", help="Check your Bedrock install and bedrock-mod-loader setup for common problems.")
    doctor_p.add_argument("--game-dir")
    doctor_p.set_defaults(func=cmd_doctor)

    export_loadout_p = sub.add_parser("export-loadout", help="Save the packs a world has enabled to a shareable JSON file.")
    export_loadout_p.add_argument("output", help="Path to write the loadout JSON file to.")
    export_loadout_p.add_argument("--world", help="World name. Remembered for next time.")
    export_loadout_p.add_argument("--game-dir")
    export_loadout_p.set_defaults(func=cmd_export_loadout)

    apply_loadout_p = sub.add_parser("apply-loadout", help="Enable every pack from a loadout JSON file that's already installed.")
    apply_loadout_p.add_argument("loadout_file", help="Path to a loadout JSON file produced by export-loadout.")
    apply_loadout_p.add_argument("--world", help="World name. Remembered for next time.")
    apply_loadout_p.add_argument("--game-dir")
    apply_loadout_p.set_defaults(func=cmd_apply_loadout)

    gui_p = sub.add_parser("gui", help="Launch the graphical interface.")
    gui_p.add_argument("--game-dir", help="Pre-fill the game directory shown in the GUI.")
    gui_p.set_defaults(func=cmd_gui)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except PackError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
