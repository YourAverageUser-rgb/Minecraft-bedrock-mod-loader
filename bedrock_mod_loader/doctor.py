"""Diagnose common problems with the local Bedrock install / bedrock-mod-loader setup."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import discovery, installer, world_config
from .packs import PackError, read_pack_info

OK = "ok"
WARN = "warn"
ERROR = "error"


@dataclass(frozen=True)
class Diagnostic:
    level: str
    message: str


def run_diagnostics(game_dir: Optional[Path]) -> list:
    results = []

    if sys.version_info < (3, 9):
        results.append(Diagnostic(ERROR, f"Python {sys.version_info.major}.{sys.version_info.minor} is unsupported; need 3.9+."))
    else:
        results.append(Diagnostic(OK, f"Python {sys.version_info.major}.{sys.version_info.minor} OK."))

    if game_dir is None:
        results.append(Diagnostic(ERROR, "No com.mojang game directory found or specified (use --game-dir / BEDROCK_GAME_DIR)."))
        return results

    if not game_dir.is_dir():
        results.append(Diagnostic(ERROR, f"Game directory does not exist: {game_dir}"))
        return results
    results.append(Diagnostic(OK, f"Game directory: {game_dir}"))

    if not os.access(game_dir, os.W_OK):
        results.append(Diagnostic(ERROR, f"Game directory is not writable: {game_dir}"))
    else:
        results.append(Diagnostic(OK, "Game directory is writable."))

    by_uuid: dict = {}
    broken = []
    for subdir in sorted(set(installer.DEV_SUBDIRS.values()) | set(installer.PROD_SUBDIRS.values())):
        root = game_dir / subdir
        if not root.is_dir():
            continue
        for pack_dir in sorted(root.iterdir()):
            if not pack_dir.is_dir():
                continue
            try:
                info = read_pack_info(pack_dir)
            except PackError as exc:
                broken.append((pack_dir, exc))
                continue
            by_uuid.setdefault(info.uuid, []).append(info)

    for pack_dir, exc in broken:
        results.append(Diagnostic(WARN, f"Unreadable manifest in {pack_dir}: {exc}"))

    for pack_uuid, infos in by_uuid.items():
        if len(infos) > 1:
            locations = ", ".join(str(i.path) for i in infos)
            results.append(Diagnostic(WARN, f"Pack uuid {pack_uuid} is installed in more than one place: {locations}"))

    if by_uuid:
        results.append(Diagnostic(OK, f"{len(by_uuid)} unique pack(s) installed."))
    elif not broken:
        results.append(Diagnostic(WARN, "No packs installed yet."))

    worlds = discovery.list_worlds(game_dir)
    if not worlds:
        results.append(Diagnostic(WARN, "No worlds found under minecraftWorlds."))
    for world_dir in worlds:
        for kind in ("behavior_pack", "resource_pack"):
            for entry in world_config.list_enabled_packs(world_dir, kind):
                pack_uuid = entry.get("pack_id")
                if pack_uuid not in by_uuid:
                    results.append(
                        Diagnostic(WARN, f"World '{world_dir.name}' enables {kind} {pack_uuid}, which isn't installed.")
                    )

    return results
