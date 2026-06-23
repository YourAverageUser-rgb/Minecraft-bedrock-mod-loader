import json

import pytest

from bedrock_mod_loader.cli import build_parser, cmd_gui, main

from .helpers import write_pack_dir, write_world_dir, zip_dir

BP_UUID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def test_install_mcpack_enables_in_world(tmp_path, capsys):
    pack_dir = write_pack_dir(tmp_path, BP_UUID, name="Cool Pack", version=(1, 0, 0))
    archive = zip_dir(pack_dir, tmp_path / "cool.mcpack")

    game_dir = tmp_path / "com.mojang"
    world_dir = game_dir / "minecraftWorlds" / "MyWorld"
    world_dir.mkdir(parents=True)

    exit_code = main([
        "install", str(archive),
        "--game-dir", str(game_dir),
        "--world", "MyWorld",
    ])

    assert exit_code == 0
    installed = game_dir / "development_behavior_packs" / "Cool_Pack"
    assert (installed / "manifest.json").is_file()

    config = json.loads((world_dir / "world_behavior_packs.json").read_text())
    assert config == [{"pack_id": BP_UUID, "version": [1, 0, 0]}]

    out = capsys.readouterr().out
    assert "installed" in out
    assert "enabled in world" in out


def test_install_unknown_world_warns_but_still_installs(tmp_path, capsys):
    pack_dir = write_pack_dir(tmp_path, BP_UUID, name="Cool Pack", version=(1, 0, 0))
    game_dir = tmp_path / "com.mojang"

    exit_code = main([
        "install", str(pack_dir),
        "--game-dir", str(game_dir),
        "--world", "DoesNotExist",
    ])

    assert exit_code == 0
    assert (game_dir / "development_behavior_packs" / "Cool_Pack" / "manifest.json").is_file()
    assert "warning: world 'DoesNotExist' not found" in capsys.readouterr().out


def test_install_prod_flag_uses_production_subdir(tmp_path):
    pack_dir = write_pack_dir(tmp_path, BP_UUID, name="Cool Pack")
    game_dir = tmp_path / "com.mojang"

    main(["install", str(pack_dir), "--game-dir", str(game_dir), "--prod"])

    assert (game_dir / "behavior_packs" / "Cool_Pack" / "manifest.json").is_file()


def test_list_packs_reports_installed_pack(tmp_path, capsys):
    pack_dir = write_pack_dir(tmp_path, BP_UUID, name="Cool Pack")
    game_dir = tmp_path / "com.mojang"
    main(["install", str(pack_dir), "--game-dir", str(game_dir)])
    capsys.readouterr()

    main(["list-packs", "--game-dir", str(game_dir)])

    out = capsys.readouterr().out
    assert "Cool Pack" in out
    assert BP_UUID in out


def test_install_bad_source_returns_error_exit_code(tmp_path, capsys):
    bogus = tmp_path / "not_a_pack.txt"
    bogus.write_text("hi", encoding="utf-8")

    exit_code = main(["install", str(bogus), "--game-dir", str(tmp_path / "com.mojang")])

    assert exit_code == 1
    assert "error:" in capsys.readouterr().err


def test_install_remembers_world_for_next_invocation(tmp_path, capsys):
    pack_dir = write_pack_dir(tmp_path, BP_UUID, name="Cool Pack")
    game_dir = tmp_path / "com.mojang"
    world_dir = game_dir / "minecraftWorlds" / "MyWorld"
    world_dir.mkdir(parents=True)

    main(["install", str(pack_dir), "--game-dir", str(game_dir), "--world", "MyWorld"])
    capsys.readouterr()

    pack_dir2 = write_pack_dir(tmp_path / "second", "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", name="Other Pack", module_type="resources")
    main(["install", str(pack_dir2), "--game-dir", str(game_dir)])

    out = capsys.readouterr().out
    assert "using remembered world 'MyWorld'" in out
    config = json.loads((world_dir / "world_resource_packs.json").read_text())
    assert config == [{"pack_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "version": [1, 0, 0]}]


def test_remembered_game_dir_used_when_flag_omitted(tmp_path, monkeypatch, capsys):
    from bedrock_mod_loader import discovery

    monkeypatch.setattr(discovery, "find_game_dirs", lambda: [])

    game_dir = tmp_path / "com.mojang"
    main(["list-packs", "--game-dir", str(game_dir)])
    capsys.readouterr()

    main(["list-packs"])

    out = capsys.readouterr().out
    assert f"No installed packs found under {game_dir}" in out


def test_info_prints_pack_details(tmp_path, capsys):
    pack_dir = write_pack_dir(tmp_path, BP_UUID, name="Cool Pack", version=(1, 2, 3))

    exit_code = main(["info", str(pack_dir)])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "[behavior_pack] Cool Pack v1.2.3" in out
    assert f"uuid: {BP_UUID}" in out
    assert "description: test pack" in out
    assert "min_engine_version: 1.21.0" in out


def test_info_prints_world(tmp_path, capsys):
    world_dir = write_world_dir(tmp_path, name="Survival World")

    main(["info", str(world_dir)])

    assert "[world] Survival World" in capsys.readouterr().out


def test_info_no_installable_content(tmp_path, capsys):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    main(["info", str(empty_dir)])

    assert "No installable content found at that source." in capsys.readouterr().out


def test_uninstall_removes_pack_and_disables_in_worlds(tmp_path, capsys):
    pack_dir = write_pack_dir(tmp_path, BP_UUID, name="Cool Pack")
    game_dir = tmp_path / "com.mojang"
    world_dir = game_dir / "minecraftWorlds" / "MyWorld"
    world_dir.mkdir(parents=True)
    main(["install", str(pack_dir), "--game-dir", str(game_dir), "--world", "MyWorld"])
    capsys.readouterr()

    exit_code = main(["uninstall", BP_UUID, "--game-dir", str(game_dir)])

    assert exit_code == 0
    assert not (game_dir / "development_behavior_packs" / "Cool_Pack").exists()
    out = capsys.readouterr().out
    assert "Removed [behavior_pack] Cool Pack" in out
    assert "disabled in world(s): MyWorld" in out


def test_enable_then_disable_pack_in_world(tmp_path, capsys):
    pack_dir = write_pack_dir(tmp_path, BP_UUID, name="Cool Pack")
    game_dir = tmp_path / "com.mojang"
    world_dir = game_dir / "minecraftWorlds" / "MyWorld"
    world_dir.mkdir(parents=True)
    main(["install", str(pack_dir), "--game-dir", str(game_dir), "--no-enable"])
    capsys.readouterr()

    main(["enable", "Cool Pack", "--world", "MyWorld", "--game-dir", str(game_dir)])
    out = capsys.readouterr().out
    assert "Enabled: [behavior_pack] Cool Pack in world 'MyWorld'" in out
    config = json.loads((world_dir / "world_behavior_packs.json").read_text())
    assert config == [{"pack_id": BP_UUID, "version": [1, 0, 0]}]

    main(["disable", "Cool Pack", "--world", "MyWorld", "--game-dir", str(game_dir)])
    out = capsys.readouterr().out
    assert "Disabled: [behavior_pack] Cool Pack in world 'MyWorld'" in out
    config = json.loads((world_dir / "world_behavior_packs.json").read_text())
    assert config == []


def test_doctor_reports_ok_for_healthy_setup(tmp_path, capsys):
    pack_dir = write_pack_dir(tmp_path, BP_UUID, name="Cool Pack")
    game_dir = tmp_path / "com.mojang"
    main(["install", str(pack_dir), "--game-dir", str(game_dir)])
    capsys.readouterr()

    exit_code = main(["doctor", "--game-dir", str(game_dir)])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "[ok]" in out
    assert "1 unique pack(s) installed" in out


def test_doctor_raises_systemexit_when_game_dir_missing(tmp_path):
    with pytest.raises(SystemExit):
        main(["doctor", "--game-dir", str(tmp_path / "does-not-exist")])


def test_export_then_apply_loadout_round_trip(tmp_path, capsys):
    pack_dir = write_pack_dir(tmp_path, BP_UUID, name="Cool Pack")
    game_dir = tmp_path / "com.mojang"
    world_dir = game_dir / "minecraftWorlds" / "MyWorld"
    world_dir.mkdir(parents=True)
    main(["install", str(pack_dir), "--game-dir", str(game_dir), "--world", "MyWorld"])
    capsys.readouterr()

    loadout_path = tmp_path / "loadout.json"
    main(["export-loadout", str(loadout_path), "--world", "MyWorld", "--game-dir", str(game_dir)])
    out = capsys.readouterr().out
    assert "Exported 1 pack(s) from world 'MyWorld'" in out
    assert loadout_path.is_file()

    main(["disable", "Cool Pack", "--world", "MyWorld", "--game-dir", str(game_dir)])
    capsys.readouterr()

    main(["apply-loadout", str(loadout_path), "--world", "MyWorld", "--game-dir", str(game_dir)])
    out = capsys.readouterr().out
    assert "enabled [behavior_pack] Cool Pack" in out
    assert "Applied 1 pack(s) to world 'MyWorld'; 0 missing." in out


def test_apply_loadout_reports_missing_pack(tmp_path, capsys):
    game_dir = tmp_path / "com.mojang"
    world_dir = game_dir / "minecraftWorlds" / "MyWorld"
    world_dir.mkdir(parents=True)

    loadout_path = tmp_path / "loadout.json"
    loadout_path.write_text(
        json.dumps(
            {
                "world": "MyWorld",
                "packs": [{"kind": "behavior_pack", "uuid": BP_UUID, "version": [1, 0, 0], "name": "Ghost Pack"}],
            }
        ),
        encoding="utf-8",
    )

    main(["apply-loadout", str(loadout_path), "--world", "MyWorld", "--game-dir", str(game_dir)])

    out = capsys.readouterr().out
    assert f"missing: [behavior_pack] Ghost Pack ({BP_UUID})" in out
    assert "Applied 0 pack(s) to world 'MyWorld'; 1 missing." in out


def test_gui_subcommand_is_registered_without_invoking_it():
    parser = build_parser()
    args = parser.parse_args(["gui"])
    assert args.func is cmd_gui
