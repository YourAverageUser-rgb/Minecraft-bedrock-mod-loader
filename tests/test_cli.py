import json

from bedrock_mod_loader.cli import main

from .helpers import write_pack_dir, zip_dir

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
