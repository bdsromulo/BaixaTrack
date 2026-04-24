"""
ffmpeg_manager.py - Centralized FFmpeg detection and auto-download.
Works both in dev mode and as a PyInstaller exe.
"""

import os
import sys
import shutil
import threading
import urllib.request
import zipfile


FFMPEG_ZIP_URL = (
    "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/"
    "ffmpeg-master-latest-win64-gpl.zip"
)


# ── Path helpers ───────────────────────────────────────────────────────────────

def _app_dir() -> str:
    """Directory where the exe or script lives."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _appdata_dir() -> str:
    base = os.environ.get("APPDATA", os.path.expanduser("~"))
    return os.path.join(base, "YouTubeMP3Extractor")


# ── Detection ──────────────────────────────────────────────────────────────────

def get_ffmpeg_location():
    """
    Returns the directory containing ffmpeg.exe to pass to yt-dlp,
    or None if ffmpeg is already in the system PATH.
    Raises FileNotFoundError if FFmpeg cannot be found anywhere.
    """
    # 1. Local ffmpeg_bin/ next to exe or script
    local = os.path.join(_app_dir(), "ffmpeg_bin")
    if os.path.isfile(os.path.join(local, "ffmpeg.exe")):
        return local

    # 2. %APPDATA%\YouTubeMP3Extractor\ffmpeg_bin\
    appdata = os.path.join(_appdata_dir(), "ffmpeg_bin")
    if os.path.isfile(os.path.join(appdata, "ffmpeg.exe")):
        return appdata

    # 3. System PATH
    if shutil.which("ffmpeg"):
        return None  # yt-dlp finds it automatically

    raise FileNotFoundError("FFmpeg não encontrado.")


def is_ffmpeg_available() -> bool:
    try:
        get_ffmpeg_location()
        return True
    except FileNotFoundError:
        return False


# ── Download ───────────────────────────────────────────────────────────────────

def download_ffmpeg(on_progress=None, on_done=None, on_error=None):
    """
    Download FFmpeg to %APPDATA%\\YouTubeMP3Extractor\\ffmpeg_bin\\ in a thread.

    Callbacks (all optional, called from the download thread):
        on_progress(pct: float)  0-100
        on_done(path: str)       directory where ffmpeg.exe was saved
        on_error(msg: str)
    """
    def _worker():
        try:
            target_dir = os.path.join(_appdata_dir(), "ffmpeg_bin")
            os.makedirs(target_dir, exist_ok=True)
            zip_path = os.path.join(target_dir, "_ffmpeg_tmp.zip")

            def _hook(count, block, total):
                if total > 0 and on_progress:
                    on_progress(min(count * block * 100 / total, 100))

            urllib.request.urlretrieve(FFMPEG_ZIP_URL, zip_path, _hook)

            with zipfile.ZipFile(zip_path, "r") as zf:
                for member in zf.namelist():
                    fname = os.path.basename(member)
                    if fname in ("ffmpeg.exe", "ffprobe.exe"):
                        src = zf.open(member)
                        dst = os.path.join(target_dir, fname)
                        with open(dst, "wb") as f:
                            import shutil as _sh
                            _sh.copyfileobj(src, f)

            try:
                os.remove(zip_path)
            except OSError:
                pass

            if on_done:
                on_done(target_dir)

        except Exception as exc:
            if on_error:
                on_error(str(exc))

    threading.Thread(target=_worker, daemon=True).start()
