import json

from bedrock_mod_loader.world_config import enable_pack_in_world

UUID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def test_enable_pack_creates_config_file(tmp_path):
    world_dir = tmp_path / "world"
    world_dir.mkdir()

    changed = enable_pack_in_world(world_dir, "behavior_pack", UUID, (1, 0, 0))

    assert changed is True
    config = json.loads((world_dir / "world_behavior_packs.json").read_text())
    assert config == [{"pack_id": UUID, "version": [1, 0, 0]}]


def test_enable_pack_is_idempotent(tmp_path):
    world_dir = tmp_path / "world"
    world_dir.mkdir()

    enable_pack_in_world(world_dir, "behavior_pack", UUID, (1, 0, 0))
    changed_again = enable_pack_in_world(world_dir, "behavior_pack", UUID, (1, 0, 0))

    assert changed_again is False
    config = json.loads((world_dir / "world_behavior_packs.json").read_text())
    assert len(config) == 1


def test_enable_pack_updates_version_in_place(tmp_path):
    world_dir = tmp_path / "world"
    world_dir.mkdir()

    enable_pack_in_world(world_dir, "behavior_pack", UUID, (1, 0, 0))
    changed = enable_pack_in_world(world_dir, "behavior_pack", UUID, (2, 0, 0))

    assert changed is True
    config = json.loads((world_dir / "world_behavior_packs.json").read_text())
    assert config == [{"pack_id": UUID, "version": [2, 0, 0]}]


def test_enable_pack_recovers_from_malformed_json(tmp_path):
    world_dir = tmp_path / "world"
    world_dir.mkdir()
    (world_dir / "world_resource_packs.json").write_text("not valid json", encoding="utf-8")

    changed = enable_pack_in_world(world_dir, "resource_pack", UUID, (1, 0, 0))

    assert changed is True
    config = json.loads((world_dir / "world_resource_packs.json").read_text())
    assert config == [{"pack_id": UUID, "version": [1, 0, 0]}]


def test_enable_pack_unsupported_kind_noop(tmp_path):
    world_dir = tmp_path / "world"
    world_dir.mkdir()

    changed = enable_pack_in_world(world_dir, "skin_pack", UUID, (1, 0, 0))

    assert changed is False
    assert not list(world_dir.iterdir())


def test_enable_pack_keeps_other_entries(tmp_path):
    world_dir = tmp_path / "world"
    world_dir.mkdir()
    other_uuid = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    (world_dir / "world_behavior_packs.json").write_text(
        json.dumps([{"pack_id": other_uuid, "version": [3, 0, 0]}]), encoding="utf-8"
    )

    enable_pack_in_world(world_dir, "behavior_pack", UUID, (1, 0, 0))

    config = json.loads((world_dir / "world_behavior_packs.json").read_text())
    assert {"pack_id": other_uuid, "version": [3, 0, 0]} in config
    assert {"pack_id": UUID, "version": [1, 0, 0]} in config
