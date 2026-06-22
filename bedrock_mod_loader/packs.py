"""Identify Bedrock pack content and unpack archives (.mcpack/.mcaddon/.mcworld/.zip)."""
from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from uuid import uuid4

PACK_ARCHIVE_EXTS = {".mcpack", ".mcaddon", ".zip"}
WORLD_ARCHIVE_EXTS = {".mcworld"}
ARCHIVE_EXTS = PACK_ARCHIVE_EXTS | WORLD_ARCHIVE_EXTS

# Maps a manifest module "type" to the kind of pack it makes up.
MODULE_KIND_MAP = {
    "data": "behavior_pack",
    "script": "behavior_pack",
    "client_data": "behavior_pack",
    "resources": "resource_pack",
    "skin_pack": "skin_pack",
    "world_template": "world_template",
}


class PackError(Exception):
    """Raised when a pack/archive cannot be identified or installed."""


@dataclass(frozen=True)
class PackInfo:
    path: Path
    kind: str
    uuid: str
    version: tuple
    name: str


def load_manifest(pack_dir: Path) -> dict:
    manifest_path = pack_dir / "manifest.json"
    try:
        with manifest_path.open(encoding="utf-8-sig") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise PackError(f"Invalid manifest.json in {pack_dir}: {exc}") from exc


def classify_manifest(manifest: dict) -> str:
    module_types = {module.get("type") for module in manifest.get("modules", [])}
    for module_type in module_types:
        kind = MODULE_KIND_MAP.get(module_type)
        if kind:
            return kind
    raise PackError(f"Could not determine pack type from modules: {sorted(t for t in module_types if t)}")


def read_pack_info(pack_dir: Path) -> PackInfo:
    manifest = load_manifest(pack_dir)
    header = manifest.get("header", {})
    pack_uuid = header.get("uuid")
    if not pack_uuid:
        raise PackError(f"manifest.json in {pack_dir} is missing header.uuid")
    version = tuple(header.get("version", [0, 0, 0]))
    name = header.get("name", pack_dir.name)
    kind = classify_manifest(manifest)
    return PackInfo(path=pack_dir, kind=kind, uuid=pack_uuid, version=version, name=name)


def is_world_save(directory: Path) -> bool:
    return (directory / "level.dat").is_file() or (directory / "db").is_dir()


def find_pack_dirs(root: Path) -> list:
    """Directories under root that directly contain a manifest.json, nearest first."""
    return sorted({p.parent for p in root.rglob("manifest.json")}, key=lambda p: len(p.parts))


def extract_archive(archive_path: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as zf:
        _safe_extract(zf, dest_dir)
    return dest_dir


def _safe_extract(zf: zipfile.ZipFile, dest_dir: Path) -> None:
    dest_resolved = dest_dir.resolve()
    for member in zf.namelist():
        member_path = (dest_dir / member).resolve()
        if dest_resolved not in member_path.parents and member_path != dest_resolved:
            raise PackError(f"Refusing to extract archive with unsafe path: {member}")
    zf.extractall(dest_dir)


def discover_sources(path: Path, scratch_root: Path) -> Iterator[Path]:
    """Yield directories that are either an installable pack (manifest.json) or a
    world save (level.dat/db), recursively extracting any archives found along the way.
    """
    if path.is_dir():
        if is_world_save(path):
            yield path
            return
        pack_dirs = find_pack_dirs(path)
        if pack_dirs:
            yield from pack_dirs
            return
        for child in sorted(path.iterdir()):
            if child.is_file() and child.suffix.lower() in ARCHIVE_EXTS:
                yield from discover_sources(child, scratch_root)
        return

    if path.is_file() and path.suffix.lower() in ARCHIVE_EXTS:
        extract_dir = scratch_root / f"{path.stem}_{uuid4().hex[:8]}"
        extract_archive(path, extract_dir)
        yield from discover_sources(extract_dir, scratch_root)
        return

    raise PackError(f"Unsupported pack source: {path}")
