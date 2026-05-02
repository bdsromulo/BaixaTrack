"""
spotify_auth.py - Spotify Authorization Code with PKCE flow.

Why PKCE: Spotify now requires user authentication for /v1/playlists/{id}/items.
Client Credentials is no longer sufficient for reading playlist content.
PKCE is the recommended flow for desktop apps with no secure backend — and
notably it does NOT require the Client Secret.

Flow:
    1. Open the user's browser to the Spotify authorize URL with a PKCE
       code_challenge and a one-shot local redirect (http://127.0.0.1:8888/callback).
    2. Run a tiny http.server on 127.0.0.1:8888 to capture the redirect with
       the auth code.
    3. POST the code + code_verifier to /api/token to get access + refresh tokens.
    4. Use refresh_token later to renew the short-lived access_token (1h TTL).
"""

import base64
import hashlib
import http.server
import secrets
import socket
import threading
import time
import urllib.parse
import webbrowser

import requests


REDIRECT_HOST = "127.0.0.1"
REDIRECT_PORT = 8888
REDIRECT_URI = f"http://{REDIRECT_HOST}:{REDIRECT_PORT}/callback"
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
# Minimum scopes to read public + user-owned playlists
SCOPES = "playlist-read-private playlist-read-collaborative"
LOGIN_TIMEOUT = 300  # seconds


class SpotifyAuthError(Exception):
    pass


def _gen_pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def _port_available(host: str, port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.bind((host, port))
        s.close()
        return True
    except OSError:
        return False


def perform_login(client_id: str, on_status=None) -> dict:
    """
    Open browser, run local callback server, exchange code for tokens.
    Returns the token dict from Spotify:
        {access_token, token_type, expires_in, refresh_token, scope}
    Blocks until the user completes the flow or LOGIN_TIMEOUT elapses.
    """
    if not client_id:
        raise SpotifyAuthError("Client ID não configurado.")

    if not _port_available(REDIRECT_HOST, REDIRECT_PORT):
        raise SpotifyAuthError(
            f"Porta {REDIRECT_PORT} ocupada. Feche o programa que está usando "
            "e tente de novo."
        )

    verifier, challenge = _gen_pkce()
    state = secrets.token_urlsafe(16)

    auth_params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
        "state": state,
        "scope": SCOPES,
    }
    auth_full_url = AUTH_URL + "?" + urllib.parse.urlencode(auth_params)

    captured: dict = {}
    done_event = threading.Event()

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != "/callback":
                self.send_response(404)
                self.end_headers()
                return
            qs = urllib.parse.parse_qs(parsed.query)
            captured["code"] = (qs.get("code") or [None])[0]
            captured["state"] = (qs.get("state") or [None])[0]
            captured["error"] = (qs.get("error") or [None])[0]

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            if captured.get("error"):
                title = "Falha na autorização"
                body = f"Spotify retornou: <code>{captured['error']}</code>."
            elif captured.get("code"):
                title = "Conectado!"
                body = "Você pode fechar esta aba e voltar ao BaixaTrack."
            else:
                title = "Resposta inesperada"
                body = "Tente novamente no app."
            html = f"""<!doctype html><meta charset="utf-8">
<title>{title}</title>
<body style="font-family:system-ui,sans-serif;background:#0F0F0F;color:#fff;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0;text-align:center">
<div><h1 style="color:#1DB954">{title}</h1><p>{body}</p></div></body>"""
            self.wfile.write(html.encode("utf-8"))
            done_event.set()

        def log_message(self, *args, **kwargs):
            pass  # silence default logging

    server = http.server.HTTPServer((REDIRECT_HOST, REDIRECT_PORT), _Handler)
    server_thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.3}, daemon=True
    )
    server_thread.start()

    try:
        if on_status:
            on_status("Abrindo navegador para login no Spotify…")
        webbrowser.open(auth_full_url)

        if not done_event.wait(timeout=LOGIN_TIMEOUT):
            raise SpotifyAuthError("Tempo esgotado aguardando login no Spotify.")
    finally:
        server.shutdown()
        server.server_close()

    if captured.get("error"):
        raise SpotifyAuthError(f"Login negado pelo Spotify: {captured['error']}")
    if captured.get("state") != state:
        raise SpotifyAuthError("Resposta inválida do Spotify (state mismatch).")
    code = captured.get("code")
    if not code:
        raise SpotifyAuthError("Código de autorização ausente na resposta.")

    if on_status:
        on_status("Trocando código por token…")

    try:
        r = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": client_id,
                "code_verifier": verifier,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
    except requests.RequestException as e:
        raise SpotifyAuthError(f"Falha de rede ao trocar code por token: {e}")

    if r.status_code != 200:
        raise SpotifyAuthError(
            f"Falha ao obter token (status {r.status_code}): {r.text[:200]}"
        )
    return r.json()


def refresh_access_token(client_id: str, refresh_token: str) -> dict:
    """
    Use the refresh_token to obtain a new short-lived access_token.
    Returns the new token dict; note Spotify MAY also return a new refresh_token.
    """
    try:
        r = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
    except requests.RequestException as e:
        raise SpotifyAuthError(f"Falha de rede ao renovar token: {e}")
    if r.status_code != 200:
        raise SpotifyAuthError(
            f"Falha ao renovar token (status {r.status_code}): {r.text[:200]}"
        )
    return r.json()
