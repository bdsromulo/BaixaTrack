"""
spotify.py - Spotify playlist import + YouTube best-match search.

Compliance notes (Spotify Developer Terms + Web API guidelines):
    - Authorization Code with PKCE flow (no Client Secret needed) — required by
      Spotify for /v1/playlists/{id}/items as of late 2024.
    - Endpoint: /v1/playlists/{id}/items (preferred over the legacy /tracks alias).
    - Honors HTTP 429 with Retry-After + exponential backoff.
    - Auto-refreshes the access token via the stored refresh_token.
    - Does not cache Spotify content beyond the immediate fetch (in-memory only).
    - Tokens stored locally per-user (%APPDATA%\\BaixaTrack); never in source.
"""

import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import requests
import yt_dlp

import config
import spotify_auth


SPOTIFY_PLAYLIST_RE = re.compile(r"(?:playlist[:/])([A-Za-z0-9]{22})")
MAX_RETRIES_429 = 4


class SpotifyError(Exception):
    pass


def is_spotify_url(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    return "open.spotify.com" in host or url.startswith("spotify:")


def extract_playlist_id(url: str) -> str | None:
    m = SPOTIFY_PLAYLIST_RE.search(url)
    return m.group(1) if m else None


def _get_access_token() -> str:
    """
    Return a valid user access token, refreshing via refresh_token if needed.
    Requires that the user has completed the PKCE login (perform_login) and
    that tokens are persisted via config.set_spotify_tokens.
    """
    client_id = config.get_spotify_client_id()
    if not client_id:
        raise SpotifyError(
            "Client ID do Spotify não configurado. Vá em ⚙ Configurações."
        )
    tokens = config.get_spotify_tokens()
    if not tokens:
        raise SpotifyError(
            "Spotify não está conectado. Vá em ⚙ Configurações e clique em "
            "\"Conectar com Spotify\"."
        )

    now = time.time()
    if tokens["access_token"] and tokens["expires_at"] > now + 60:
        return tokens["access_token"]

    # Refresh
    try:
        new = spotify_auth.refresh_access_token(client_id, tokens["refresh_token"])
    except spotify_auth.SpotifyAuthError as e:
        raise SpotifyError(
            f"Não foi possível renovar a sessão do Spotify: {e}\n\n"
            "Reconecte em ⚙ Configurações."
        )
    access = new.get("access_token")
    if not access:
        raise SpotifyError("Resposta de refresh sem access_token.")
    expires_at = time.time() + int(new.get("expires_in", 3600))
    refresh = new.get("refresh_token")  # Spotify may rotate it
    config.update_spotify_access_token(access, expires_at, refresh_token=refresh)
    return access


# ── Authenticated GET with 429 backoff and JSON-error extraction ──────────────
def _spotify_message(resp: requests.Response) -> str:
    """Pull the real error.message field from a Spotify error JSON, if present."""
    try:
        body = resp.json()
        err = body.get("error") or {}
        msg = err.get("message")
        if msg:
            return str(msg)
    except Exception:
        pass
    return resp.text[:300] if resp.text else ""


def _spotify_get(url: str, headers: dict, params: dict | None = None) -> requests.Response:
    """GET with Retry-After + exponential backoff on 429, per Spotify guidelines."""
    delay = 1.0
    last_resp = None
    for attempt in range(MAX_RETRIES_429 + 1):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=20)
        except requests.RequestException as e:
            raise SpotifyError(f"Falha de rede: {e}")
        last_resp = resp
        if resp.status_code != 429:
            return resp
        retry_after = resp.headers.get("Retry-After")
        try:
            wait = float(retry_after) if retry_after else delay
        except ValueError:
            wait = delay
        time.sleep(min(wait, 30.0))
        delay *= 2
    return last_resp  # caller decides what to do with the final 429


# ── Playlist fetch ─────────────────────────────────────────────────────────────
def fetch_playlist(
    url: str,
    on_page=None,
    cancel_event: "threading.Event | None" = None,
) -> dict:
    """
    Returns {"name": str, "tracks": [{"name": str, "artist": str}, ...]}.
    Uses /v1/playlists/{id}/items with a user access token (PKCE).

    on_page(loaded:int, total:int) is invoked after each page so the GUI can
    show progress on very large playlists. cancel_event, if set between pages,
    short-circuits the loop and returns whatever was collected so far.
    """
    pid = extract_playlist_id(url)
    if not pid:
        raise SpotifyError("URL do Spotify não reconhecida (esperado playlist).")

    token = _get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    # ── Playlist metadata ────────────────────────────────────────────────────
    meta = _spotify_get(
        f"https://api.spotify.com/v1/playlists/{pid}",
        headers=headers,
        params={"fields": "name"},
    )
    if meta.status_code == 404:
        raise SpotifyError("Playlist não encontrada ou privada.")
    if meta.status_code == 401:
        raise SpotifyError(
            "Token rejeitado (401). Verifique Client ID/Secret nas Configurações."
        )
    if meta.status_code != 200:
        api_msg = _spotify_message(meta) or "(sem mensagem)"
        raise SpotifyError(
            f"Spotify retornou {meta.status_code} ao ler a playlist.\n\n"
            f"Mensagem da API: {api_msg}"
        )

    name = meta.json().get("name", "Playlist")

    # ── Items (tracks + episodes) ────────────────────────────────────────────
    tracks: list[dict] = []
    items_url = f"https://api.spotify.com/v1/playlists/{pid}/items"
    params = {
        "limit": "100",
    }
    next_url: str | None = items_url
    refreshed_once = False
    total_items = 0

    while next_url:
        if cancel_event is not None and cancel_event.is_set():
            break
        # Use params only for the first call; subsequent next_url already has them encoded.
        r = _spotify_get(next_url, headers=headers, params=params if next_url == items_url else None)

        # 401: force a token refresh once, then retry
        if r.status_code == 401 and not refreshed_once:
            refreshed_once = True
            tokens = config.get_spotify_tokens() or {}
            # Force expiry so _get_access_token refreshes
            config.update_spotify_access_token("", 0.0, refresh_token=tokens.get("refresh_token"))
            try:
                token = _get_access_token()
            except SpotifyError as e:
                raise
            headers = {"Authorization": f"Bearer {token}"}
            continue

        if r.status_code == 401:
            api_msg = _spotify_message(r) or "(sem mensagem)"
            raise SpotifyError(
                f"Token rejeitado (401) ao listar itens da playlist.\n\n"
                f"Mensagem da API: {api_msg}\n\n"
                "Reconecte sua conta em ⚙ Configurações → Conectar com Spotify."
            )
        if r.status_code == 404:
            raise SpotifyError("Playlist não encontrada ao listar itens.")
        if r.status_code != 200:
            api_msg = _spotify_message(r) or "(sem mensagem)"
            hint = ""
            if r.status_code == 403:
                hint = (
                    "\n\nObs.: 403 costuma ocorrer com playlists editoriais "
                    "da Spotify (Today's Top Hits etc.) ou se a playlist não "
                    "estiver realmente pública."
                )
            raise SpotifyError(
                f"Spotify retornou {r.status_code} ao listar itens.\n\n"
                f"Mensagem da API: {api_msg}{hint}"
            )
        body = r.json()
        if not total_items:
            total_items = int(body.get("total") or 0)
        items = body.get("items", []) or []
        for item in items:
            # Spotify returns track data under "track" by default, but uses
            # "item" when additional_types is specified or in some response
            # variations. Check both.
            tr = (item or {}).get("track") or (item or {}).get("item")
            if not tr:
                continue
            t_type = tr.get("type")
            if t_type and t_type != "track":
                continue  # skip episodes
            tname = (tr.get("name") or "").strip()
            artists = tr.get("artists") or []
            aname = ", ".join(a.get("name", "") for a in artists if a.get("name")).strip()
            if not (tname and aname):
                continue
            tracks.append({"name": tname, "artist": aname})
        if on_page:
            on_page(len(tracks), total_items or len(tracks))
        next_url = body.get("next")

    return {"name": name, "tracks": tracks}


# ── YouTube search ─────────────────────────────────────────────────────────────
def _search_one(track: dict, cancel_event: "threading.Event | None" = None) -> dict | None:
    if cancel_event is not None and cancel_event.is_set():
        return None
    query = f"ytsearch1:{track['name']} {track['artist']} (AUDIO)"
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
        "default_search": "ytsearch1",
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(query, download=False)
    except Exception:
        return None
    if not info:
        return None
    entries = info.get("entries") or []
    if not entries:
        return None
    e = entries[0]
    if not e:
        return None
    vid = e.get("id", "")
    return {
        "id": vid,
        "title": e.get("title", f"{track['name']} - {track['artist']}"),
        "duration": e.get("duration"),
        "thumbnail": e.get("thumbnail") or (
            f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if vid else ""
        ),
        "url": e.get("url") or (f"https://www.youtube.com/watch?v={vid}" if vid else ""),
        "_spotify_origin": True,
        "_spotify_track": f"{track['name']} - {track['artist']}",
    }


def search_youtube_for_tracks(
    tracks: list[dict],
    on_progress=None,
    max_workers: int = 5,
    cancel_event: "threading.Event | None" = None,
) -> list[dict]:
    """
    Returns entries in the same format as downloader.get_info.
    Tracks with no YouTube match are skipped silently.
    on_progress(done:int, total:int, current_label:str)

    If cancel_event is set during the run, queued futures are cancelled and the
    function returns whatever was matched up to that point (already in playlist
    order). The 5 in-flight yt-dlp lookups still complete before return.
    """
    results: list[tuple[int, dict]] = []
    total = len(tracks)
    done = 0

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {
            ex.submit(_search_one, t, cancel_event): (i, t)
            for i, t in enumerate(tracks)
        }
        cancelled = False
        for fut in as_completed(futures):
            if cancel_event is not None and cancel_event.is_set():
                cancelled = True
                break
            i, t = futures[fut]
            entry = fut.result()
            done += 1
            if on_progress:
                on_progress(done, total, f"{t['name']} - {t['artist']}")
            if entry:
                results.append((i, entry))
        if cancelled:
            for f in futures:
                f.cancel()

    results.sort(key=lambda x: x[0])
    return [e for _, e in results]
