"""Fixture helpers shared across tests for building fake Bedrock packs."""
import json
import zipfile
from pathlib import Path

NIL_MODULE_UUID = "11111111-1111-1111-1111-111111111111"


def make_manifest(pack_uuid: str, name="Test Pack", version=(1, 0, 0), module_type="data") -> dict:
    return {
        "format_version": 2,
        "header": {
            "name": name,
            "description": "test pack",
            "uuid": pack_uuid,
            "version": list(version),
            "min_engine_version": [1, 21, 0],
        },
        "modules": [{"type": module_type, "uuid": NIL_MODULE_UUID, "version": list(version)}],
    }


def write_pack_dir(root: Path, pack_uuid: str, name="Test Pack", version=(1, 0, 0), module_type="data") -> Path:
    pack_dir = root / "pack_src"
    pack_dir.mkdir(parents=True, exist_ok=True)
    manifest = make_manifest(pack_uuid, name=name, version=version, module_type=module_type)
    (pack_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return pack_dir


def zip_dir(src_dir: Path, archive_path: Path, root_in_zip: bool = False) -> Path:
    """Zip the contents of src_dir. If root_in_zip, nest everything under src_dir.name/."""
    with zipfile.ZipFile(archive_path, "w") as zf:
        for file in src_dir.rglob("*"):
            if file.is_file():
                arcname = file.relative_to(src_dir.parent) if root_in_zip else file.relative_to(src_dir)
                zf.write(file, arcname)
    return archive_path


def write_world_dir(root: Path, name="My World") -> Path:
    world_dir = root / "world_src"
    world_dir.mkdir(parents=True, exist_ok=True)
    (world_dir / "level.dat").write_bytes(b"\x00" * 8)
    (world_dir / "levelname.txt").write_text(name, encoding="utf-8")
    (world_dir / "db").mkdir(exist_ok=True)
    return world_dir
