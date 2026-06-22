from bedrock_mod_loader.installer import install_pack, install_world, sanitize_name, target_subdir
from bedrock_mod_loader.packs import PackError, PackInfo, read_pack_info

from .helpers import write_pack_dir, write_world_dir

BP_UUID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
OTHER_UUID = "cccccccc-cccc-cccc-cccc-cccccccccccc"


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
