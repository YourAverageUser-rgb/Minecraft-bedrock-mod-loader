"""Locate Minecraft Bedrock's com.mojang game directory and worlds on the host."""
from __future__ import annotations

import os
import platform
from pathlib import Path

WINDOWS_PACKAGE_IDS = (
    "Microsoft.MinecraftUWP_8wekyb3d8bbwe",
    "Microsoft.MinecraftWindowsBeta_8wekyb3d8bbwe",
    "Microsoft.MinecraftEducationEdition_8wekyb3d8bbwe",
    "Microsoft.MinecraftEducationPreview_8wekyb3d8bbwe",
)


def candidate_game_dirs() -> list:
    candidates = []

    env_override = os.environ.get("BEDROCK_GAME_DIR")
    if env_override:
        candidates.append(Path(env_override))

    system = platform.system()
    if system == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            packages_root = Path(local_app_data) / "Packages"
            for package_id in WINDOWS_PACKAGE_IDS:
                candidates.append(packages_root / package_id / "LocalState" / "games" / "com.mojang")
    elif system == "Darwin":
        candidates.append(Path.home() / "Library" / "Application Support" / "mcpelauncher" / "games" / "com.mojang")
    elif system == "Linux":
        home = Path.home()
        candidates.append(home / ".local" / "share" / "mcpelauncher" / "games" / "com.mojang")
        candidates.append(home / ".var" / "app" / "io.mrarm.mcpelauncher" / "data" / "mcpelauncher" / "games" / "com.mojang")
        candidates.append(Path("/storage/emulated/0/Android/data/com.mojang.minecraftpe/files/games/com.mojang"))

    return candidates


def find_game_dirs() -> list:
    seen = set()
    result = []
    for candidate in candidate_game_dirs():
        if candidate.is_dir() and candidate not in seen:
            seen.add(candidate)
            result.append(candidate)
    return result


def list_worlds(game_dir: Path) -> list:
    worlds_root = game_dir / "minecraftWorlds"
    if not worlds_root.is_dir():
        return []
    return sorted(p for p in worlds_root.iterdir() if p.is_dir())


def find_world_by_name(game_dir: Path, name: str):
    worlds_root = game_dir / "minecraftWorlds"
    if not worlds_root.is_dir():
        return None

    direct = worlds_root / name
    if direct.is_dir():
        return direct

    for world_dir in worlds_root.iterdir():
        if not world_dir.is_dir():
            continue
        levelname_file = world_dir / "levelname.txt"
        if levelname_file.is_file():
            try:
                label = levelname_file.read_text(encoding="utf-8", errors="ignore").strip()
            except OSError:
                continue
            if label == name:
                return world_dir
    return None
