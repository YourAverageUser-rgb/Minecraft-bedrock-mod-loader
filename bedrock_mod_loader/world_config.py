"""Enable installed packs inside a world so Minecraft loads them automatically.

Copying a pack into development_behavior_packs/development_resource_packs makes it
available, but a world only actually loads it once its UUID+version is listed in
that world's world_behavior_packs.json / world_resource_packs.json.
"""
from __future__ import annotations

import json
from pathlib import Path

CONFIG_FILENAMES = {
    "behavior_pack": "world_behavior_packs.json",
    "resource_pack": "world_resource_packs.json",
}


def enable_pack_in_world(world_dir: Path, kind: str, pack_uuid: str, version: tuple) -> bool:
    """Add/update pack_uuid@version in the world's pack list. Returns True if changed."""
    filename = CONFIG_FILENAMES.get(kind)
    if filename is None:
        return False

    config_path = world_dir / filename
    entries = []
    if config_path.is_file():
        try:
            entries = json.loads(config_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            entries = []
        if not isinstance(entries, list):
            entries = []

    version_list = list(version)
    for entry in entries:
        if entry.get("pack_id") == pack_uuid:
            if list(entry.get("version", [])) == version_list:
                return False
            entry["version"] = version_list
            break
    else:
        entries.append({"pack_id": pack_uuid, "version": version_list})

    config_path.write_text(json.dumps(entries, indent=4) + "\n", encoding="utf-8")
    return True
