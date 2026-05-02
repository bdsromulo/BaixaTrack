"""
config.py - User-local configuration storage.
Lives outside the repo (in %APPDATA%\\BaixaTrack on Windows, ~/.config/BaixaTrack elsewhere).
Stores Spotify credentials and any other per-user settings.
"""

import json
import os
import sys
import tempfile


APP_NAME = "BaixaTrack"


def _config_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    path = os.path.join(base, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def _config_file() -> str:
    return os.path.join(_config_dir(), "config.json")


def load() -> dict:
    path = _config_file()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except (json.JSONDecodeError, OSError):
        return {}


def save(data: dict) -> None:
    path = _config_file()
    fd, tmp = tempfile.mkstemp(prefix=".cfg_", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def get_spotify_client_id() -> str | None:
    data = load()
    sp = data.get("spotify") or {}
    cid = (sp.get("client_id") or "").strip()
    return cid or None


def set_spotify_client_id(client_id: str) -> None:
    data = load()
    sp = data.get("spotify") or {}
    sp["client_id"] = client_id.strip()
    data["spotify"] = sp
    save(data)


def get_spotify_tokens() -> dict | None:
    """Returns {access_token, refresh_token, expires_at} or None."""
    data = load()
    sp = data.get("spotify") or {}
    if sp.get("access_token") and sp.get("refresh_token"):
        return {
            "access_token": sp["access_token"],
            "refresh_token": sp["refresh_token"],
            "expires_at": float(sp.get("expires_at", 0)),
        }
    return None


def set_spotify_tokens(access_token: str, refresh_token: str, expires_at: float) -> None:
    data = load()
    sp = data.get("spotify") or {}
    sp["access_token"] = access_token
    sp["refresh_token"] = refresh_token
    sp["expires_at"] = float(expires_at)
    data["spotify"] = sp
    save(data)


def update_spotify_access_token(access_token: str, expires_at: float, refresh_token: str | None = None) -> None:
    data = load()
    sp = data.get("spotify") or {}
    sp["access_token"] = access_token
    sp["expires_at"] = float(expires_at)
    if refresh_token:
        sp["refresh_token"] = refresh_token
    data["spotify"] = sp
    save(data)


def clear_spotify_credentials() -> None:
    data = load()
    if "spotify" in data:
        data.pop("spotify")
        save(data)


def is_spotify_connected() -> bool:
    return get_spotify_tokens() is not None
