import zipfile

import pytest

from bedrock_mod_loader.packs import (
    PackError,
    classify_manifest,
    discover_sources,
    is_world_save,
    read_pack_info,
)

from .helpers import write_pack_dir, write_world_dir, zip_dir

BP_UUID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
RP_UUID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def test_classify_manifest_behavior_pack():
    assert classify_manifest({"modules": [{"type": "data"}]}) == "behavior_pack"
    assert classify_manifest({"modules": [{"type": "script"}]}) == "behavior_pack"


def test_classify_manifest_resource_pack():
    assert classify_manifest({"modules": [{"type": "resources"}]}) == "resource_pack"


def test_classify_manifest_unknown_raises():
    with pytest.raises(PackError):
        classify_manifest({"modules": [{"type": "mystery"}]})


def test_read_pack_info_from_directory(tmp_path):
    pack_dir = write_pack_dir(tmp_path, BP_UUID, name="My BP", version=(2, 1, 0), module_type="data")
    info = read_pack_info(pack_dir)
    assert info.kind == "behavior_pack"
    assert info.uuid == BP_UUID
    assert info.version == (2, 1, 0)
    assert info.name == "My BP"


def test_read_pack_info_missing_uuid_raises(tmp_path):
    pack_dir = tmp_path / "broken"
    pack_dir.mkdir()
    (pack_dir / "manifest.json").write_text('{"header": {}, "modules": [{"type": "data"}]}', encoding="utf-8")
    with pytest.raises(PackError):
        read_pack_info(pack_dir)


def test_is_world_save(tmp_path):
    world_dir = write_world_dir(tmp_path)
    assert is_world_save(world_dir) is True
    assert is_world_save(tmp_path) is False


def test_discover_sources_plain_directory(tmp_path):
    pack_dir = write_pack_dir(tmp_path, BP_UUID)
    scratch = tmp_path / "scratch"
    found = list(discover_sources(pack_dir, scratch))
    assert found == [pack_dir]


def test_discover_sources_mcpack_archive(tmp_path):
    pack_dir = write_pack_dir(tmp_path, BP_UUID)
    archive = zip_dir(pack_dir, tmp_path / "addon.mcpack")
    scratch = tmp_path / "scratch"
    found = list(discover_sources(archive, scratch))
    assert len(found) == 1
    info = read_pack_info(found[0])
    assert info.uuid == BP_UUID


def test_discover_sources_mcaddon_with_two_packs(tmp_path):
    bp_dir = write_pack_dir(tmp_path / "bp_build", BP_UUID, name="Addon BP", module_type="data")
    rp_dir = write_pack_dir(tmp_path / "rp_build", RP_UUID, name="Addon RP", module_type="resources")

    addon_root = tmp_path / "addon_root"
    (addon_root / "BP").mkdir(parents=True)
    (addon_root / "RP").mkdir(parents=True)
    (addon_root / "BP" / "manifest.json").write_text((bp_dir / "manifest.json").read_text(), encoding="utf-8")
    (addon_root / "RP" / "manifest.json").write_text((rp_dir / "manifest.json").read_text(), encoding="utf-8")

    archive = zip_dir(addon_root, tmp_path / "addon.mcaddon")
    scratch = tmp_path / "scratch"
    found = list(discover_sources(archive, scratch))
    kinds = sorted(read_pack_info(p).kind for p in found)
    assert kinds == ["behavior_pack", "resource_pack"]


def test_discover_sources_double_zipped_mcaddon(tmp_path):
    pack_dir = write_pack_dir(tmp_path, BP_UUID)
    inner_mcpack = zip_dir(pack_dir, tmp_path / "inner.mcpack")

    outer_root = tmp_path / "outer_root"
    outer_root.mkdir()
    (outer_root / "inner.mcpack").write_bytes(inner_mcpack.read_bytes())
    outer_archive = zip_dir(outer_root, tmp_path / "outer.mcaddon")

    scratch = tmp_path / "scratch"
    found = list(discover_sources(outer_archive, scratch))
    assert len(found) == 1
    assert read_pack_info(found[0]).uuid == BP_UUID


def test_discover_sources_mcworld_archive(tmp_path):
    world_dir = write_world_dir(tmp_path, name="Survival World")
    archive = zip_dir(world_dir, tmp_path / "save.mcworld", root_in_zip=False)
    scratch = tmp_path / "scratch"
    found = list(discover_sources(archive, scratch))
    assert len(found) == 1
    assert is_world_save(found[0])


def test_discover_sources_rejects_zip_slip(tmp_path):
    archive_path = tmp_path / "evil.mcpack"
    with zipfile.ZipFile(archive_path, "w") as zf:
        zf.writestr("../../evil.txt", "pwned")
    scratch = tmp_path / "scratch"
    with pytest.raises(PackError):
        list(discover_sources(archive_path, scratch))


def test_discover_sources_unsupported_extension(tmp_path):
    bogus = tmp_path / "readme.txt"
    bogus.write_text("hello", encoding="utf-8")
    with pytest.raises(PackError):
        list(discover_sources(bogus, tmp_path / "scratch"))
