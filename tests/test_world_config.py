import json

from bedrock_mod_loader.world_config import (
    disable_pack_in_world,
    enable_pack_in_world,
    list_enabled_packs,
    restore_backup,
)

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


def test_disable_pack_removes_entry(tmp_path):
    world_dir = tmp_path / "world"
    world_dir.mkdir()
    enable_pack_in_world(world_dir, "behavior_pack", UUID, (1, 0, 0))

    changed = disable_pack_in_world(world_dir, "behavior_pack", UUID)

    assert changed is True
    assert list_enabled_packs(world_dir, "behavior_pack") == []


def test_disable_pack_not_enabled_is_noop(tmp_path):
    world_dir = tmp_path / "world"
    world_dir.mkdir()

    changed = disable_pack_in_world(world_dir, "behavior_pack", UUID)

    assert changed is False


def test_list_enabled_packs_unsupported_kind_returns_empty(tmp_path):
    world_dir = tmp_path / "world"
    world_dir.mkdir()
    assert list_enabled_packs(world_dir, "skin_pack") == []


def test_enable_pack_creates_backup_of_previous_config(tmp_path):
    world_dir = tmp_path / "world"
    world_dir.mkdir()
    other_uuid = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    enable_pack_in_world(world_dir, "behavior_pack", other_uuid, (1, 0, 0))
    enable_pack_in_world(world_dir, "behavior_pack", UUID, (1, 0, 0))

    backup_path = world_dir / "world_behavior_packs.json.bak"
    assert backup_path.is_file()
    backup_config = json.loads(backup_path.read_text())
    assert backup_config == [{"pack_id": other_uuid, "version": [1, 0, 0]}]


def test_restore_backup_undoes_last_write(tmp_path):
    world_dir = tmp_path / "world"
    world_dir.mkdir()
    other_uuid = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    enable_pack_in_world(world_dir, "behavior_pack", other_uuid, (1, 0, 0))
    enable_pack_in_world(world_dir, "behavior_pack", UUID, (1, 0, 0))

    restored = restore_backup(world_dir, "behavior_pack")

    assert restored is True
    assert list_enabled_packs(world_dir, "behavior_pack") == [{"pack_id": other_uuid, "version": [1, 0, 0]}]


def test_restore_backup_without_prior_backup_returns_false(tmp_path):
    world_dir = tmp_path / "world"
    world_dir.mkdir()
    assert restore_backup(world_dir, "behavior_pack") is False
