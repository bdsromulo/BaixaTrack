"""
history.py - Per-user download history.
Stored alongside config.json under %APPDATA%\\BaixaTrack (Windows) or ~/.config/BaixaTrack.
Keyed by YouTube video_id (the only stable, exact identifier).
Lookup is O(1) via dict — no fuzzy matching.
"""

import json
import os
import tempfile
from datetime import datetime, timezone

from config import _config_dir


def _history_file() -> str:
    return os.path.join(_config_dir(), "history.json")


_cache: dict | None = None


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    path = _history_file()
    if not os.path.exists(path):
        _cache = {"downloads": {}}
        return _cache
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        if "downloads" not in data or not isinstance(data["downloads"], dict):
            data["downloads"] = {}
        _cache = data
    except (json.JSONDecodeError, OSError):
        _cache = {"downloads": {}}
    return _cache


def _save() -> None:
    if _cache is None:
        return
    path = _history_file()
    fd, tmp = tempfile.mkstemp(prefix=".hist_", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(_cache, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def is_downloaded(video_id: str) -> bool:
    if not video_id:
        return False
    return video_id in _load()["downloads"]


def mark_downloaded(video_id: str, title: str = "", path: str = "") -> None:
    if not video_id:
        return
    data = _load()
    data["downloads"][video_id] = {
        "title": title,
        "path": path,
        "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    _save()


def remove(video_id: str) -> None:
    data = _load()
    if video_id in data["downloads"]:
        data["downloads"].pop(video_id)
        _save()


def count() -> int:
    return len(_load()["downloads"])
