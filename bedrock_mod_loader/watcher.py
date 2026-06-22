"""Poll a drop folder and hand off any new, fully-written entry to a handler."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional, Set


def scan_ready(drop_dir: Path, processed: Set[str], min_age: float, now: Optional[float] = None) -> list:
    """Top-level entries in drop_dir not yet processed and untouched for min_age seconds."""
    now = time.time() if now is None else now
    ready = []
    for entry in sorted(drop_dir.iterdir()):
        if entry.name in processed:
            continue
        try:
            mtime = entry.stat().st_mtime
        except FileNotFoundError:
            continue
        if now - mtime < min_age:
            continue
        ready.append(entry)
    return ready


def watch_forever(
    drop_dir: Path,
    handler: Callable[[Path], None],
    poll_interval: float = 2.0,
    min_age: float = 1.5,
    max_iterations: Optional[int] = None,
) -> None:
    processed: Set[str] = set()
    iterations = 0
    while max_iterations is None or iterations < max_iterations:
        for entry in scan_ready(drop_dir, processed, min_age):
            processed.add(entry.name)
            handler(entry)
        iterations += 1
        if max_iterations is None or iterations < max_iterations:
            time.sleep(poll_interval)
