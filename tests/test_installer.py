from bedrock_mod_loader.installer import (
    find_installed_pack,
    install_pack,
    install_world,
    iter_installed_packs,
    sanitize_name,
    target_subdir,
    uninstall_pack,
    world_display_name,
)
from bedrock_mod_loader.packs import PackError, PackInfo, read_pack_info

from .helpers import write_pack_dir, write_world_dir

BP_UUID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
OTHER_UUID = "cccccccc-cccc-cccc-cccc-cccccccccccc"
RP_UUID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def test_target_subdir_dev_vs_prod():
    assert target_subdir("behavior_pack", dev=True) == "development_behavior_packs"
    assert target_subdir("behavior_pack", dev=False) == "behavior_packs"
    assert target_subdir("resource_pack", dev=True) == "development_resource_packs"


def test_sanitize_name_strips_unsafe_chars():
    assert sanitize_name("My / Cool Pack!!") == "My_Cool_Pack"
    assert sanitize_name("") == "pack"


def test_install_pack_fresh_install(tmp_path):
    pack_dir = write_pack_dir(tmp_path, BP_UUID, name="Cool Pack", version=(1, 0, 0))
    game_dir = tmp_path / "com.mojang"

    result = install_pack(read_pack_info(pack_dir), game_dir, dev=True)

    assert result.action == "installed"
    assert (result.installed_path / "manifest.json").is_file()
    assert result.installed_path.parent.name == "development_behavior_packs"


def test_install_pack_skips_when_up_to_date(tmp_path):
    pack_dir = write_pack_dir(tmp_path, BP_UUID, version=(1, 0, 0))
    game_dir = tmp_path / "com.mojang"

    install_pack(read_pack_info(pack_dir), game_dir, dev=True)
    result = install_pack(read_pack_info(pack_dir), game_dir, dev=True)

    assert result.action == "skipped (up to date)"


def test_install_pack_skips_older_version_without_force(tmp_path):
    new_pack = write_pack_dir(tmp_path / "new", BP_UUID, version=(2, 0, 0))
    install_pack(read_pack_info(new_pack), tmp_path / "com.mojang", dev=True)

    old_pack = write_pack_dir(tmp_path / "old", BP_UUID, version=(1, 0, 0))
    result = install_pack(read_pack_info(old_pack), tmp_path / "com.mojang", dev=True)

    assert result.action == "skipped (newer already installed)"
    assert read_pack_info(result.installed_path).version == (2, 0, 0)


def test_install_pack_upgrades_to_newer_version(tmp_path):
    v1 = write_pack_dir(tmp_path / "v1", BP_UUID, version=(1, 0, 0))
    install_pack(read_pack_info(v1), tmp_path / "com.mojang", dev=True)

    v2 = write_pack_dir(tmp_path / "v2", BP_UUID, version=(2, 0, 0))
    result = install_pack(read_pack_info(v2), tmp_path / "com.mojang", dev=True)

    assert result.action == "updated"
    assert read_pack_info(result.installed_path).version == (2, 0, 0)


def test_install_pack_force_reinstalls_same_version(tmp_path):
    pack_dir = write_pack_dir(tmp_path, BP_UUID, version=(1, 0, 0))
    game_dir = tmp_path / "com.mojang"

    install_pack(read_pack_info(pack_dir), game_dir, dev=True)
    result = install_pack(read_pack_info(pack_dir), game_dir, dev=True, force=True)

    assert result.action == "updated"


def test_install_pack_disambiguates_name_collision(tmp_path):
    first = write_pack_dir(tmp_path / "first", BP_UUID, name="Shared Name")
    install_pack(read_pack_info(first), tmp_path / "com.mojang", dev=True)

    second = write_pack_dir(tmp_path / "second", OTHER_UUID, name="Shared Name")
    result = install_pack(read_pack_info(second), tmp_path / "com.mojang", dev=True)

    assert result.action == "installed"
    assert result.installed_path.name == f"Shared_Name_{OTHER_UUID[:8]}"


def test_install_pack_invalid_kind_raises(tmp_path):
    pack_dir = write_pack_dir(tmp_path, BP_UUID)
    info = read_pack_info(pack_dir)
    bad_info = PackInfo(path=info.path, kind="world_template", uuid=info.uuid, version=info.version, name=info.name)
    try:
        install_pack(bad_info, tmp_path / "com.mojang")
        assert False, "expected PackError"
    except PackError:
        pass


def test_install_world_fresh(tmp_path):
    world_dir = write_world_dir(tmp_path, name="My World")
    dest = install_world(world_dir, tmp_path / "com.mojang")
    assert dest.name == "My_World"
    assert (dest / "level.dat").is_file()


def test_install_world_collision_creates_unique_folder(tmp_path):
    world_dir = write_world_dir(tmp_path, name="My World")
    first = install_world(world_dir, tmp_path / "com.mojang")
    second = install_world(world_dir, tmp_path / "com.mojang")
    assert first != second
    assert second.is_dir()


def test_install_world_force_overwrites(tmp_path):
    world_dir = write_world_dir(tmp_path, name="My World")
    first = install_world(world_dir, tmp_path / "com.mojang")
    second = install_world(world_dir, tmp_path / "com.mojang", force=True)
    assert first == second


def test_world_display_name_falls_back_to_dir_name(tmp_path):
    world_dir = tmp_path / "world_src"
    world_dir.mkdir()
    assert world_display_name(world_dir) == "world_src"


def test_iter_installed_packs_finds_dev_and_prod(tmp_path):
    game_dir = tmp_path / "com.mojang"
    dev_pack = write_pack_dir(tmp_path / "dev", BP_UUID, name="Dev Pack")
    install_pack(read_pack_info(dev_pack), game_dir, dev=True)
    prod_pack = write_pack_dir(tmp_path / "prod", RP_UUID, name="Prod Pack", module_type="resources")
    install_pack(read_pack_info(prod_pack), game_dir, dev=False)

    found = {info.uuid: info for info in iter_installed_packs(game_dir)}

    assert set(found) == {BP_UUID, RP_UUID}


def test_iter_installed_packs_skips_unreadable_manifest(tmp_path):
    game_dir = tmp_path / "com.mojang"
    broken_dir = game_dir / "development_behavior_packs" / "broken"
    broken_dir.mkdir(parents=True)
    (broken_dir / "manifest.json").write_text("not json", encoding="utf-8")

    assert list(iter_installed_packs(game_dir)) == []


def test_find_installed_pack_by_uuid_prefix(tmp_path):
    game_dir = tmp_path / "com.mojang"
    pack_dir = write_pack_dir(tmp_path, BP_UUID, name="Cool Pack")
    install_pack(read_pack_info(pack_dir), game_dir, dev=True)

    info = find_installed_pack(game_dir, BP_UUID[:8])

    assert info.uuid == BP_UUID


def test_find_installed_pack_by_name_substring(tmp_path):
    game_dir = tmp_path / "com.mojang"
    pack_dir = write_pack_dir(tmp_path, BP_UUID, name="Cool Pack")
    install_pack(read_pack_info(pack_dir), game_dir, dev=True)

    info = find_installed_pack(game_dir, "cool")

    assert info.uuid == BP_UUID


def test_find_installed_pack_no_match_raises(tmp_path):
    game_dir = tmp_path / "com.mojang"
    try:
        find_installed_pack(game_dir, "nope")
        assert False, "expected PackError"
    except PackError:
        pass


def test_find_installed_pack_ambiguous_match_raises(tmp_path):
    game_dir = tmp_path / "com.mojang"
    first = write_pack_dir(tmp_path / "first", BP_UUID, name="Shared Pack")
    install_pack(read_pack_info(first), game_dir, dev=True)
    second = write_pack_dir(tmp_path / "second", OTHER_UUID, name="Shared Pack")
    install_pack(read_pack_info(second), game_dir, dev=True)

    try:
        find_installed_pack(game_dir, "shared")
        assert False, "expected PackError"
    except PackError as exc:
        assert "multiple" in str(exc)


def test_uninstall_pack_removes_directory(tmp_path):
    game_dir = tmp_path / "com.mojang"
    pack_dir = write_pack_dir(tmp_path, BP_UUID, name="Cool Pack")
    result = install_pack(read_pack_info(pack_dir), game_dir, dev=True)

    uninstall_pack(read_pack_info(result.installed_path))

    assert not result.installed_path.exists()
