"""Export/apply shareable "loadouts" -- a JSON snapshot of which packs a world
enables, by UUID+version, that someone else can drop on top of their own
installed packs to recreate your setup.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from . import world_config
from .packs import PackInfo

LOADOUT_KINDS = ("behavior_pack", "resource_pack")


@dataclass(frozen=True)
class LoadoutEntry:
    kind: str
    uuid: str
    version: tuple
    name: str = ""


@dataclass(frozen=True)
class ApplyResult:
    applied: tuple
    missing: tuple


def build_loadout(world_dir: Path, installed_by_uuid: Optional[Dict[str, PackInfo]] = None) -> dict:
    """Snapshot a world's currently-enabled packs into a loadout dict."""
    installed_by_uuid = installed_by_uuid or {}
    packs = []
    for kind in LOADOUT_KINDS:
        for entry in world_config.list_enabled_packs(world_dir, kind):
            pack_uuid = entry.get("pack_id")
            version = list(entry.get("version", []))
            info = installed_by_uuid.get(pack_uuid)
            packs.append({"kind": kind, "uuid": pack_uuid, "version": version, "name": info.name if info else ""})
    return {"world": world_dir.name, "packs": packs}


def write_loadout(loadout: dict, dest: Path) -> None:
    dest.write_text(json.dumps(loadout, indent=2) + "\n", encoding="utf-8")


def read_loadout(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def apply_loadout(loadout: dict, world_dir: Path, installed_by_uuid: Dict[str, PackInfo]) -> ApplyResult:
    """Enable every pack in the loadout that's already installed; report the rest as missing."""
    applied = []
    missing = []
    for entry in loadout.get("packs", []):
        kind = entry.get("kind")
        pack_uuid = entry.get("uuid")
        info = installed_by_uuid.get(pack_uuid)
        if info is None:
            missing.append(LoadoutEntry(kind=kind, uuid=pack_uuid, version=tuple(entry.get("version", [])), name=entry.get("name", "")))
            continue
        world_config.enable_pack_in_world(world_dir, kind, info.uuid, info.version)
        applied.append(LoadoutEntry(kind=kind, uuid=info.uuid, version=info.version, name=info.name))
    return ApplyResult(applied=tuple(applied), missing=tuple(missing))
