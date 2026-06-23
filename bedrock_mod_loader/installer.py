"""Copy identified packs and world saves into the right com.mojang subfolder."""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
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


def world_display_name(world_dir: Path) -> str:
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
    name = sanitize_name(world_display_name(world_dir))
    dest = worlds_root / name

    if dest.exists():
        if force:
            shutil.rmtree(dest)
        else:
            dest = worlds_root / f"{name}_{uuid4().hex[:8]}"

    shutil.copytree(world_dir, dest)
    return dest


def iter_installed_packs(game_dir: Path) -> Iterator[PackInfo]:
    """Yield PackInfo for every readable pack under any dev/prod subfolder."""
    subdirs = sorted(set(DEV_SUBDIRS.values()) | set(PROD_SUBDIRS.values()))
    for subdir in subdirs:
        root = game_dir / subdir
        if not root.is_dir():
            continue
        for pack_dir in sorted(root.iterdir()):
            if not pack_dir.is_dir():
                continue
            try:
                yield read_pack_info(pack_dir)
            except PackError:
                continue


def find_installed_pack(game_dir: Path, identifier: str) -> PackInfo:
    """Look up an installed pack by UUID (full or prefix) or by a name substring."""
    identifier_lower = identifier.lower()
    matches = {}
    for info in iter_installed_packs(game_dir):
        if info.uuid.lower() == identifier_lower or info.uuid.lower().startswith(identifier_lower):
            matches[info.path] = info
        elif identifier_lower in info.name.lower():
            matches[info.path] = info

    if not matches:
        raise PackError(f"No installed pack matches '{identifier}'")
    if len(matches) > 1:
        options = ", ".join(f"{m.name} ({m.uuid})" for m in matches.values())
        raise PackError(f"'{identifier}' matches multiple installed packs: {options}")
    return next(iter(matches.values()))


def uninstall_pack(info: PackInfo) -> None:
    """Delete an installed pack's files from disk."""
    shutil.rmtree(info.path)
