import time

from bedrock_mod_loader.watcher import scan_ready, watch_forever


def test_scan_ready_skips_fresh_files(tmp_path):
    new_file = tmp_path / "pack.mcpack"
    new_file.write_bytes(b"data")

    ready = scan_ready(tmp_path, processed=set(), min_age=60, now=time.time())

    assert ready == []


def test_scan_ready_returns_stable_files(tmp_path):
    old_file = tmp_path / "pack.mcpack"
    old_file.write_bytes(b"data")

    ready = scan_ready(tmp_path, processed=set(), min_age=0, now=time.time() + 10)

    assert ready == [old_file]


def test_scan_ready_excludes_already_processed(tmp_path):
    old_file = tmp_path / "pack.mcpack"
    old_file.write_bytes(b"data")

    ready = scan_ready(tmp_path, processed={"pack.mcpack"}, min_age=0, now=time.time() + 10)

    assert ready == []


def test_watch_forever_invokes_handler_once_per_entry(tmp_path):
    (tmp_path / "a.mcpack").write_bytes(b"data")
    (tmp_path / "b.mcpack").write_bytes(b"data")
    seen = []

    watch_forever(tmp_path, handler=seen.append, poll_interval=0, min_age=0, max_iterations=3)

    assert sorted(p.name for p in seen) == ["a.mcpack", "b.mcpack"]


def test_watch_forever_picks_up_new_file_on_later_iteration(tmp_path):
    seen = []

    watch_forever(tmp_path, handler=seen.append, poll_interval=0, min_age=0, max_iterations=1)
    (tmp_path / "late.mcpack").write_bytes(b"data")
    watch_forever(tmp_path, handler=seen.append, poll_interval=0, min_age=0, max_iterations=1)

    assert [p.name for p in seen] == ["late.mcpack"]
