from bedrock_mod_loader import doctor, installer, world_config

from .helpers import write_pack_dir

BP_UUID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
OTHER_UUID = "cccccccc-cccc-cccc-cccc-cccccccccccc"


def test_run_diagnostics_no_game_dir_reports_error():
    results = doctor.run_diagnostics(None)
    assert any(r.level == doctor.ERROR for r in results)


def test_run_diagnostics_missing_directory_reports_error(tmp_path):
    results = doctor.run_diagnostics(tmp_path / "does-not-exist")
    assert any(r.level == doctor.ERROR and "does not exist" in r.message for r in results)


def test_run_diagnostics_healthy_install_reports_ok(tmp_path):
    game_dir = tmp_path / "com.mojang"
    game_dir.mkdir()
    pack_dir = write_pack_dir(tmp_path, BP_UUID, name="Cool Pack")
    from bedrock_mod_loader.packs import read_pack_info

    installer.install_pack(read_pack_info(pack_dir), game_dir, dev=True)

    results = doctor.run_diagnostics(game_dir)

    assert not any(r.level == doctor.ERROR for r in results)
    assert any("1 unique pack(s) installed" in r.message for r in results)


def test_run_diagnostics_flags_duplicate_uuid_install(tmp_path):
    game_dir = tmp_path / "com.mojang"
    game_dir.mkdir()
    from bedrock_mod_loader.packs import read_pack_info

    dev_pack = write_pack_dir(tmp_path / "dev", BP_UUID, name="Cool Pack")
    installer.install_pack(read_pack_info(dev_pack), game_dir, dev=True)
    prod_pack = write_pack_dir(tmp_path / "prod", BP_UUID, name="Cool Pack")
    installer.install_pack(read_pack_info(prod_pack), game_dir, dev=False)

    results = doctor.run_diagnostics(game_dir)

    assert any(r.level == doctor.WARN and "more than one place" in r.message for r in results)


def test_run_diagnostics_flags_orphaned_world_reference(tmp_path):
    game_dir = tmp_path / "com.mojang"
    world_dir = game_dir / "minecraftWorlds" / "MyWorld"
    world_dir.mkdir(parents=True)
    world_config.enable_pack_in_world(world_dir, "behavior_pack", OTHER_UUID, (1, 0, 0))

    results = doctor.run_diagnostics(game_dir)

    assert any(r.level == doctor.WARN and OTHER_UUID in r.message for r in results)


def test_run_diagnostics_warns_when_no_packs_installed(tmp_path):
    game_dir = tmp_path / "com.mojang"
    game_dir.mkdir()

    results = doctor.run_diagnostics(game_dir)

    assert any(r.level == doctor.WARN and "No packs installed" in r.message for r in results)
