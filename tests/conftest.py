import pytest


@pytest.fixture(autouse=True)
def isolated_user_config(tmp_path, monkeypatch):
    """Never let tests read/write the real ~/.bedrock_mod_loader/config.json."""
    monkeypatch.setenv("BEDROCK_MOD_LOADER_CONFIG", str(tmp_path / "_user_config.json"))
