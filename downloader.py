"""
downloader.py - YouTube audio download engine using yt-dlp
"""

import os
import threading
import yt_dlp
from ffmpeg_manager import get_ffmpeg_location


class DownloadError(Exception):
    pass


class YoutubeDownloader:
    def __init__(self):
        self._cancel_event = threading.Event()

    def cancel(self):
        self._cancel_event.set()

    def reset(self):
        self._cancel_event.clear()

    def get_info(self, url: str) -> dict:
        """
        Fetch metadata for a video or playlist URL without downloading.
        Returns a dict with keys:
            'type': 'video' | 'playlist'
            'title': str
            'entries': list of {id, title, duration, thumbnail, url}
        """
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "skip_download": True,
            "ignoreerrors": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
            except Exception as e:
                raise DownloadError(f"Erro ao obter informações: {e}")

        if info is None:
            raise DownloadError("Não foi possível obter informações da URL.")

        # Playlist
        if info.get("_type") == "playlist" or "entries" in info:
            entries = []
            for entry in info.get("entries", []):
                if entry is None:
                    continue
                entries.append(
                    {
                        "id": entry.get("id", ""),
                        "title": entry.get("title", "Sem título"),
                        "duration": entry.get("duration"),
                        "thumbnail": entry.get("thumbnail", ""),
                        "url": entry.get("url") or entry.get("webpage_url") or f"https://www.youtube.com/watch?v={entry.get('id', '')}",
                    }
                )
            return {
                "type": "playlist",
                "title": info.get("title", "Playlist"),
                "entries": entries,
            }

        # Single video
        return {
            "type": "video",
            "title": info.get("title", "Sem título"),
            "entries": [
                {
                    "id": info.get("id", ""),
                    "title": info.get("title", "Sem título"),
                    "duration": info.get("duration"),
                    "thumbnail": info.get("thumbnail", ""),
                    "url": url,
                }
            ],
        }

    def download_entries(
        self,
        entries: list,
        output_dir: str,
        on_progress=None,
        on_entry_start=None,
        on_entry_done=None,
        on_error=None,
    ):
        """
        Download a list of entries as MP3 files.
        Callbacks:
            on_progress(index, total, percent, speed, eta)
            on_entry_start(index, total, title)
            on_entry_done(index, total, title, filepath)
            on_error(index, title, message)
        """
        self.reset()
        total = len(entries)

        for idx, entry in enumerate(entries):
            if self._cancel_event.is_set():
                break

            title = entry.get("title", f"Faixa {idx + 1}")
            url = entry["url"]

            if on_entry_start:
                on_entry_start(idx, total, title)

            def make_progress_hook(i, t, ttl):
                def hook(d):
                    if self._cancel_event.is_set():
                        raise yt_dlp.utils.DownloadCancelled()
                    if d["status"] == "downloading" and on_progress:
                        raw = d.get("_percent_str", "0%").strip().replace("%", "")
                        try:
                            pct = float(raw)
                        except ValueError:
                            pct = 0.0
                        speed = d.get("_speed_str", "").strip()
                        eta = d.get("_eta_str", "").strip()
                        on_progress(i, t, pct, speed, eta)
                return hook

            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
                "quiet": True,
                "no_warnings": True,
                "progress_hooks": [make_progress_hook(idx, total, title)],
                "ignoreerrors": False,
            }
            try:
                ffmpeg_loc = get_ffmpeg_location()
                if ffmpeg_loc:
                    ydl_opts["ffmpeg_location"] = ffmpeg_loc
            except FileNotFoundError:
                pass  # let yt-dlp try on its own


            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

                if on_entry_done:
                    on_entry_done(idx, total, title, output_dir)

            except yt_dlp.utils.DownloadCancelled:
                break
            except Exception as e:
                if on_error:
                    on_error(idx, title, str(e))

    @staticmethod
    def format_duration(seconds) -> str:
        if seconds is None:
            return "?"
        seconds = int(seconds)
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"
