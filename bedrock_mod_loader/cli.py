"""Command line interface for bedrock-mod-loader."""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from . import discovery, installer, world_config
from .packs import PackError, discover_sources, is_world_save, read_pack_info


def resolve_game_dir(args) -> Path:
    if args.game_dir:
        game_dir = Path(args.game_dir)
        game_dir.mkdir(parents=True, exist_ok=True)
        return game_dir
    found = discovery.find_game_dirs()
    if not found:
        raise SystemExit(
            "Could not auto-detect a Minecraft Bedrock game directory (com.mojang).\n"
            "Pass --game-dir explicitly, or set the BEDROCK_GAME_DIR environment variable."
        )
    return found[0]


def _format_version(version) -> str:
    return ".".join(str(part) for part in version)


def _install_one(source: Path, game_dir: Path, scratch: Path, dev: bool, force: bool, world_dir, enable: bool) -> None:
    for found in discover_sources(source, scratch):
        if is_world_save(found):
            dest = installer.install_world(found, game_dir, force=force)
            print(f"[world] installed '{found.name}' -> {dest}")
            continue

        info = read_pack_info(found)
        result = installer.install_pack(info, game_dir, dev=dev, force=force)
        print(f"[{result.kind}] {result.name} v{_format_version(result.version)}: {result.action} -> {result.installed_path}")

        if enable and world_dir is not None and result.action.startswith(("installed", "updated")):
            changed = world_config.enable_pack_in_world(world_dir, result.kind, result.uuid, result.version)
            if changed:
                print(f"    enabled in world '{world_dir.name}'")


def cmd_install(args) -> None:
    game_dir = resolve_game_dir(args)
    world_dir = None
    if args.world:
        world_dir = discovery.find_world_by_name(game_dir, args.world)
        if world_dir is None:
            print(f"warning: world '{args.world}' not found under {game_dir}; packs will install but won't be enabled.")

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

    world_dir = discovery.find_world_by_name(game_dir, args.world) if args.world else None
    if args.world and world_dir is None:
        print(f"warning: world '{args.world}' not found yet; packs will install but won't be enabled until it exists.")

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
    subdirs = list(installer.DEV_SUBDIRS.values()) + list(installer.PROD_SUBDIRS.values())
    found_any = False
    for subdir in subdirs:
        root = game_dir / subdir
        if not root.is_dir():
            continue
        for pack_dir in sorted(root.iterdir()):
            if not pack_dir.is_dir():
                continue
            try:
                info = read_pack_info(pack_dir)
            except PackError:
                continue
            found_any = True
            print(f"[{subdir}] {info.name}  uuid={info.uuid}  v{_format_version(info.version)}")
    if not found_any:
        print(f"No installed packs found under {game_dir}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bedrock-mod-loader", description="Install and auto-load Minecraft Bedrock mod packs and resources.")
    sub = parser.add_subparsers(dest="command", required=True)

    install_p = sub.add_parser("install", help="Install one or more packs, addons, or world saves.")
    install_p.add_argument("sources", nargs="+", help="Path(s) to a pack folder, .mcpack, .mcaddon, .mcworld, or .zip file.")
    install_p.add_argument("--game-dir", help="Path to the com.mojang directory (auto-detected if omitted).")
    install_p.add_argument("--world", help="World name (folder or display name) to auto-enable installed packs in.")
    install_p.add_argument("--prod", action="store_true", help="Install into behavior_packs/resource_packs instead of development_*.")
    install_p.add_argument("--no-enable", action="store_true", help="Install without enabling in the target world.")
    install_p.add_argument("--force", action="store_true", help="Overwrite even if an equal or newer version is already installed.")
    install_p.set_defaults(func=cmd_install)

    watch_p = sub.add_parser("watch", help="Watch a folder and auto-install/enable any pack dropped into it.")
    watch_p.add_argument("source", help="Folder to watch for new packs.")
    watch_p.add_argument("--game-dir", help="Path to the com.mojang directory (auto-detected if omitted).")
    watch_p.add_argument("--world", help="World name (folder or display name) to auto-enable installed packs in.")
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
