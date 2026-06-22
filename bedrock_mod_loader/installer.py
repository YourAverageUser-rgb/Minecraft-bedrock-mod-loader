"""Copy identified packs and world saves into the right com.mojang subfolder."""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .packs import PackError, PackInfo, read_pack_info

DEV_SUBDIRS = {
    "behavior_pack": "development_behavior_packs",
    "resource_pack": "development_resource_packs",
    "skin_pack": "development_skin_packs",
}
PROD_SUBDIRS = {
    "behavior_pack": "behavior_packs",
    "resource_pack": "resource_packs",
    "skin_pack": "skin_packs",
}


@dataclass(frozen=True)
class InstallResult:
    kind: str
    name: str
    uuid: str
    version: tuple
    installed_path: Path
    action: str  # "installed" | "updated" | "skipped (up to date)" | "skipped (newer already installed)"


def target_subdir(kind: str, dev: bool) -> str:
    mapping = DEV_SUBDIRS if dev else PROD_SUBDIRS
    if kind not in mapping:
        raise PackError(f"Unsupported pack kind for install: {kind}")
    return mapping[kind]


def sanitize_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9 _.-]", "", name).strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned or "pack"


def _read_existing_pack(dest: Path):
    try:
        return read_pack_info(dest)
    except PackError:
        return None


def install_pack(info: PackInfo, game_dir: Path, dev: bool = True, force: bool = False) -> InstallResult:
    subdir = target_subdir(info.kind, dev)
    dest_root = game_dir / subdir
    dest_root.mkdir(parents=True, exist_ok=True)
    dest = dest_root / sanitize_name(info.name)

    existing = _read_existing_pack(dest) if dest.exists() else None

    if existing is not None and existing.uuid == info.uuid:
        if not force and existing.version >= info.version:
            action = "skipped (up to date)" if existing.version == info.version else "skipped (newer already installed)"
            return InstallResult(info.kind, info.name, info.uuid, existing.version, dest, action)
        action = "updated"
    elif existing is not None:
        # Folder name collides with a differently-uuid'd pack; disambiguate.
        dest = dest_root / f"{sanitize_name(info.name)}_{info.uuid[:8]}"
        action = "installed"
    else:
        action = "installed"

    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(info.path, dest)
    return InstallResult(info.kind, info.name, info.uuid, info.version, dest, action)


def _world_display_name(world_dir: Path) -> str:
    levelname_file = world_dir / "levelname.txt"
    if levelname_file.is_file():
        try:
            label = levelname_file.read_text(encoding="utf-8", errors="ignore").strip()
        except OSError:
            label = ""
        if label:
            return label
    return world_dir.name


def install_world(world_dir: Path, game_dir: Path, force: bool = False) -> Path:
    worlds_root = game_dir / "minecraftWorlds"
    worlds_root.mkdir(parents=True, exist_ok=True)
    name = sanitize_name(_world_display_name(world_dir))
    dest = worlds_root / name

    if dest.exists():
        if force:
            shutil.rmtree(dest)
        else:
            dest = worlds_root / f"{name}_{uuid4().hex[:8]}"

    shutil.copytree(world_dir, dest)
    return dest
