from bedrock_mod_loader.discovery import candidate_game_dirs, find_world_by_name, list_worlds


def test_candidate_game_dirs_honors_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("BEDROCK_GAME_DIR", str(tmp_path / "custom"))
    candidates = candidate_game_dirs()
    assert candidates[0] == tmp_path / "custom"


def test_list_worlds_empty_when_missing(tmp_path):
    assert list_worlds(tmp_path / "com.mojang") == []


def test_list_worlds_lists_world_folders(tmp_path):
    game_dir = tmp_path / "com.mojang"
    (game_dir / "minecraftWorlds" / "WorldA").mkdir(parents=True)
    (game_dir / "minecraftWorlds" / "WorldB").mkdir(parents=True)

    worlds = list_worlds(game_dir)

    assert [w.name for w in worlds] == ["WorldA", "WorldB"]


def test_find_world_by_name_matches_folder_name(tmp_path):
    game_dir = tmp_path / "com.mojang"
    world_dir = game_dir / "minecraftWorlds" / "Abc123"
    world_dir.mkdir(parents=True)

    assert find_world_by_name(game_dir, "Abc123") == world_dir


def test_find_world_by_name_matches_levelname_txt(tmp_path):
    game_dir = tmp_path / "com.mojang"
    world_dir = game_dir / "minecraftWorlds" / "Abc123"
    world_dir.mkdir(parents=True)
    (world_dir / "levelname.txt").write_text("My Survival World", encoding="utf-8")

    assert find_world_by_name(game_dir, "My Survival World") == world_dir


def test_find_world_by_name_returns_none_when_missing(tmp_path):
    game_dir = tmp_path / "com.mojang"
    (game_dir / "minecraftWorlds").mkdir(parents=True)

    assert find_world_by_name(game_dir, "Nope") is None
