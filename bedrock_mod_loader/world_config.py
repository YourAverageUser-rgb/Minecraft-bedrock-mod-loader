"""Enable installed packs inside a world so Minecraft loads them automatically.

Copying a pack into development_behavior_packs/development_resource_packs makes it
available, but a world only actually loads it once its UUID+version is listed in
that world's world_behavior_packs.json / world_resource_packs.json.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

CONFIG_FILENAMES = {
    "behavior_pack": "world_behavior_packs.json",
    "resource_pack": "world_resource_packs.json",
}


def _read_entries(config_path: Path) -> list:
    if not config_path.is_file():
        return []
    try:
        entries = json.loads(config_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return []
    return entries if isinstance(entries, list) else []


def _write_entries(config_path: Path, entries: list) -> None:
    """Write the pack list, keeping a one-deep .bak of whatever was there before."""
    if config_path.is_file():
        shutil.copy2(config_path, config_path.with_suffix(config_path.suffix + ".bak"))
    config_path.write_text(json.dumps(entries, indent=4) + "\n", encoding="utf-8")


def enable_pack_in_world(world_dir: Path, kind: str, pack_uuid: str, version: tuple) -> bool:
    """Add/update pack_uuid@version in the world's pack list. Returns True if changed."""
    filename = CONFIG_FILENAMES.get(kind)
    if filename is None:
        return False

    config_path = world_dir / filename
    entries = _read_entries(config_path)

    version_list = list(version)
    for entry in entries:
        if entry.get("pack_id") == pack_uuid:
            if list(entry.get("version", [])) == version_list:
                return False
            entry["version"] = version_list
            break
    else:
        entries.append({"pack_id": pack_uuid, "version": version_list})

    _write_entries(config_path, entries)
    return True


def disable_pack_in_world(world_dir: Path, kind: str, pack_uuid: str) -> bool:
    """Remove pack_uuid from the world's pack list (files on disk are untouched). Returns True if changed."""
    filename = CONFIG_FILENAMES.get(kind)
    if filename is None:
        return False

    config_path = world_dir / filename
    entries = _read_entries(config_path)
    remaining = [entry for entry in entries if entry.get("pack_id") != pack_uuid]
    if len(remaining) == len(entries):
        return False

    _write_entries(config_path, remaining)
    return True


def list_enabled_packs(world_dir: Path, kind: str) -> list:
    """Raw [{"pack_id": ..., "version": [...]}, ...] entries a world currently enables."""
    filename = CONFIG_FILENAMES.get(kind)
    if filename is None:
        return []
    return _read_entries(world_dir / filename)


def restore_backup(world_dir: Path, kind: str) -> bool:
    """Undo the most recent enable/disable for this kind by restoring its .bak file."""
    filename = CONFIG_FILENAMES.get(kind)
    if filename is None:
        return False
    config_path = world_dir / filename
    backup_path = config_path.with_suffix(config_path.suffix + ".bak")
    if not backup_path.is_file():
        return False
    shutil.copy2(backup_path, config_path)
    return True
