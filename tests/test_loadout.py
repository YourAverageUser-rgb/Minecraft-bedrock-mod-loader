from bedrock_mod_loader import world_config
from bedrock_mod_loader.loadout import apply_loadout, build_loadout, read_loadout, write_loadout
from bedrock_mod_loader.packs import PackInfo

BP_UUID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
RP_UUID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
MISSING_UUID = "cccccccc-cccc-cccc-cccc-cccccccccccc"


def _info(uuid, kind="behavior_pack", name="Some Pack", version=(1, 0, 0)):
    return PackInfo(path=None, kind=kind, uuid=uuid, version=version, name=name)


def test_build_loadout_snapshots_enabled_packs(tmp_path):
    world_dir = tmp_path / "world"
    world_dir.mkdir()
    world_config.enable_pack_in_world(world_dir, "behavior_pack", BP_UUID, (1, 0, 0))
    world_config.enable_pack_in_world(world_dir, "resource_pack", RP_UUID, (2, 0, 0))

    installed = {BP_UUID: _info(BP_UUID, name="Cool BP"), RP_UUID: _info(RP_UUID, kind="resource_pack", name="Cool RP")}
    data = build_loadout(world_dir, installed)

    assert data["world"] == "world"
    packs = {p["uuid"]: p for p in data["packs"]}
    assert packs[BP_UUID] == {"kind": "behavior_pack", "uuid": BP_UUID, "version": [1, 0, 0], "name": "Cool BP"}
    assert packs[RP_UUID]["name"] == "Cool RP"


def test_build_loadout_names_blank_when_not_installed(tmp_path):
    world_dir = tmp_path / "world"
    world_dir.mkdir()
    world_config.enable_pack_in_world(world_dir, "behavior_pack", BP_UUID, (1, 0, 0))

    data = build_loadout(world_dir)

    assert data["packs"] == [{"kind": "behavior_pack", "uuid": BP_UUID, "version": [1, 0, 0], "name": ""}]


def test_write_and_read_loadout_roundtrip(tmp_path):
    data = {"world": "world", "packs": [{"kind": "behavior_pack", "uuid": BP_UUID, "version": [1, 0, 0], "name": "Cool BP"}]}
    dest = tmp_path / "loadout.json"

    write_loadout(data, dest)

    assert read_loadout(dest) == data


def test_apply_loadout_enables_installed_packs_and_reports_missing(tmp_path):
    world_dir = tmp_path / "world"
    world_dir.mkdir()
    data = {
        "world": "world",
        "packs": [
            {"kind": "behavior_pack", "uuid": BP_UUID, "version": [1, 0, 0], "name": "Cool BP"},
            {"kind": "behavior_pack", "uuid": MISSING_UUID, "version": [1, 0, 0], "name": "Gone Pack"},
        ],
    }
    installed = {BP_UUID: _info(BP_UUID, name="Cool BP")}

    result = apply_loadout(data, world_dir, installed)

    assert [e.uuid for e in result.applied] == [BP_UUID]
    assert [e.uuid for e in result.missing] == [MISSING_UUID]
    assert result.missing[0].name == "Gone Pack"

    enabled = world_config.list_enabled_packs(world_dir, "behavior_pack")
    assert enabled == [{"pack_id": BP_UUID, "version": [1, 0, 0]}]
