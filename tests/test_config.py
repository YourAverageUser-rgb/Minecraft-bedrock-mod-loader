from bedrock_mod_loader import config


def test_load_config_missing_file_returns_empty_dict():
    assert config.load_config() == {}


def test_update_config_persists_and_merges(tmp_path):
    config.update_config(game_dir="/some/path")
    config.update_config(last_world="MyWorld")

    data = config.load_config()
    assert data == {"game_dir": "/some/path", "last_world": "MyWorld"}


def test_update_config_overwrites_existing_key():
    config.update_config(last_world="First")
    config.update_config(last_world="Second")

    assert config.load_config()["last_world"] == "Second"


def test_update_config_ignores_none_values():
    config.update_config(game_dir="/some/path")
    config.update_config(game_dir=None)

    assert config.load_config()["game_dir"] == "/some/path"


def test_load_config_recovers_from_malformed_json():
    path = config.config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not valid json", encoding="utf-8")

    assert config.load_config() == {}


def test_save_config_creates_parent_directories():
    path = config.config_path()
    assert not path.exists()

    config.save_config({"a": 1})

    assert path.is_file()
