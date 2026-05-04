"""
app.py - Main GUI application for YouTube MP3 Extractor
Built with customtkinter for a modern dark-mode interface.
Compatible with PyInstaller (sys._MEIPASS resource paths).
"""

import os
import sys
import threading
import time
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageTk
import requests
from io import BytesIO

from downloader import YoutubeDownloader, DownloadError
import ffmpeg_manager
import history
import config
import spotify
import spotify_auth

# ── PyInstaller resource helper ────────────────────────────────────────────────
def resource_path(rel: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


# ── Theme ──────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

ACCENT   = "#EF4444"
BG_DARK  = "#0F0F0F"
BG_CARD  = "#1A1A1A"
BG_ITEM  = "#232323"
TEXT_MAIN = "#FFFFFF"
TEXT_SUB  = "#AAAAAA"
GREEN    = "#22C55E"
YELLOW   = "#EAB308"


# ── Helper ─────────────────────────────────────────────────────────────────────
def load_thumbnail(url: str, size=(72, 72)):
    try:
        r = requests.get(url, timeout=5)
        img = Image.open(BytesIO(r.content)).convert("RGB")
        img.thumbnail(size, Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception:
        return None


# ── FFmpeg Setup Dialog ────────────────────────────────────────────────────────
class FFmpegSetupDialog(ctk.CTkToplevel):
    """
    Modal dialog shown on first launch if FFmpeg is missing.
    Offers to download FFmpeg automatically.
    """
    def __init__(self, master, on_complete):
        super().__init__(master)
        self.on_complete = on_complete
        self.title("Configuração inicial — FFmpeg")
        self.geometry("500x300")
        self.resizable(False, False)
        self.configure(fg_color=BG_CARD)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_skip)

        # Center over parent
        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width()  - 500) // 2
        y = master.winfo_y() + (master.winfo_height() - 300) // 2
        self.geometry(f"+{x}+{y}")

        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self, text="⚠  FFmpeg não encontrado",
            font=("Inter", 16, "bold"), text_color=YELLOW
        ).grid(row=0, column=0, pady=(28, 8), padx=24)

        ctk.CTkLabel(
            self,
            text=(
                "O FFmpeg é necessário para converter o áudio para MP3.\n"
                "Clique em Baixar para instalá-lo automaticamente (~170 MB).\n"
                "O download é feito uma única vez."
            ),
            font=("Inter", 12), text_color=TEXT_SUB,
            justify="center"
        ).grid(row=1, column=0, pady=(0, 20), padx=24)

        self.progress = ctk.CTkProgressBar(
            self, fg_color=BG_ITEM, progress_color=ACCENT, height=8
        )
        self.progress.set(0)
        self.progress.grid(row=2, column=0, padx=32, sticky="ew")
        self.progress.grid_remove()

        self.status_lbl = ctk.CTkLabel(
            self, text="", font=("Inter", 11), text_color=TEXT_SUB
        )
        self.status_lbl.grid(row=3, column=0, pady=(6, 0))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=4, column=0, pady=24)

        self.download_btn = ctk.CTkButton(
            btn_frame, text="⬇  Baixar FFmpeg", width=160, height=40,
            font=("Inter", 13, "bold"), fg_color=ACCENT, hover_color="#DC2626",
            command=self._start_download
        )
        self.download_btn.pack(side="left", padx=8)

        ctk.CTkButton(
            btn_frame, text="Pular", width=80, height=40,
            font=("Inter", 12), fg_color=BG_ITEM, hover_color="#333333",
            command=self._on_skip
        ).pack(side="left", padx=8)

    def _start_download(self):
        self.download_btn.configure(state="disabled", text="Baixando…")
        self.progress.grid()
        self.status_lbl.configure(text="Conectando…")

        ffmpeg_manager.download_ffmpeg(
            on_progress=self._on_progress,
            on_done=self._on_done,
            on_error=self._on_error,
        )

    def _on_progress(self, pct: float):
        self.after(0, lambda: self.progress.set(pct / 100))
        self.after(0, lambda: self.status_lbl.configure(
            text=f"Baixando FFmpeg… {pct:.0f}%"
        ))

    def _on_done(self, path: str):
        self.after(0, self._finish)

    def _finish(self):
        self.progress.set(1)
        self.status_lbl.configure(text="✓ FFmpeg instalado com sucesso!", text_color=GREEN)
        self.after(1200, lambda: (self.destroy(), self.on_complete()))

    def _on_error(self, msg: str):
        self.after(0, lambda: messagebox.showerror(
            "Erro no download", f"Não foi possível baixar o FFmpeg:\n{msg}", parent=self
        ))
        self.after(0, lambda: self.download_btn.configure(state="normal", text="⬇  Tentar novamente"))

    def _on_skip(self):
        self.destroy()
        self.on_complete()


# ── Settings Dialog ────────────────────────────────────────────────────────────
class SettingsDialog(ctk.CTkToplevel):
    """Per-user settings — Spotify integration via PKCE."""

    def __init__(self, master):
        super().__init__(master)
        self.title("Configurações")
        self.geometry("580x520")
        self.resizable(False, False)
        self.configure(fg_color=BG_CARD)
        self.grab_set()

        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width()  - 580) // 2
        y = master.winfo_y() + (master.winfo_height() - 520) // 2
        self.geometry(f"+{x}+{y}")

        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self, text="🎵  Conta Spotify",
            font=("Inter", 16, "bold"), text_color=TEXT_MAIN
        ).grid(row=0, column=0, pady=(24, 4), padx=24, sticky="w")

        ctk.CTkLabel(
            self,
            text=(
                "O BaixaTrack usa o fluxo PKCE do Spotify (login no navegador).\n"
                "Você precisa criar um app gratuito no painel do Spotify uma vez:\n\n"
                "1. Acesse developer.spotify.com/dashboard e crie um app\n"
                "2. Em \"Which API/SDKs\" marque apenas Web API\n"
                "3. Em Redirect URIs adicione: http://127.0.0.1:8888/callback\n"
                "4. Copie o Client ID abaixo (Client Secret NÃO é necessário)\n"
                "5. Clique em \"Conectar com Spotify\" — o navegador abrirá."
            ),
            font=("Inter", 11), text_color=TEXT_SUB,
            justify="left", anchor="w", wraplength=520,
        ).grid(row=1, column=0, padx=24, pady=(0, 12), sticky="w")

        cid = config.get_spotify_client_id() or ""

        ctk.CTkLabel(self, text="Client ID", font=("Inter", 12, "bold"),
                     text_color=TEXT_SUB).grid(row=2, column=0, padx=24, sticky="w")
        self.id_entry = ctk.CTkEntry(
            self, height=36, font=("Inter", 12),
            fg_color=BG_ITEM, border_color="#333333", text_color=TEXT_MAIN,
        )
        self.id_entry.grid(row=3, column=0, padx=24, pady=(2, 12), sticky="ew")
        self.id_entry.insert(0, cid)

        # Status row
        status_frame = ctk.CTkFrame(self, fg_color=BG_ITEM, corner_radius=8)
        status_frame.grid(row=4, column=0, padx=24, pady=(4, 8), sticky="ew")
        status_frame.grid_columnconfigure(0, weight=1)

        self.status_lbl = ctk.CTkLabel(
            status_frame, text="", font=("Inter", 12),
            text_color=TEXT_MAIN, anchor="w",
        )
        self.status_lbl.grid(row=0, column=0, padx=12, pady=10, sticky="w")
        self._refresh_status()

        # Action buttons
        action_row = ctk.CTkFrame(self, fg_color="transparent")
        action_row.grid(row=5, column=0, padx=24, pady=(0, 8), sticky="ew")
        action_row.grid_columnconfigure(0, weight=1)

        self.connect_btn = ctk.CTkButton(
            action_row, text="🔗  Conectar com Spotify", height=40,
            font=("Inter", 13, "bold"),
            fg_color="#1DB954", hover_color="#1AA34A",
            command=self._connect,
        )
        self.connect_btn.grid(row=0, column=0, sticky="ew")

        self.disconnect_btn = ctk.CTkButton(
            action_row, text="Desconectar", height=32,
            font=("Inter", 11), fg_color=BG_ITEM, hover_color="#333333",
            text_color=TEXT_MAIN, command=self._disconnect,
        )
        self.disconnect_btn.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        # Bottom buttons
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=6, column=0, padx=24, pady=(16, 16), sticky="ew")
        btn_row.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            btn_row, text="Fechar", width=100, height=36,
            font=("Inter", 12, "bold"),
            fg_color=ACCENT, hover_color="#DC2626",
            command=self.destroy,
        ).grid(row=0, column=0, sticky="e")

    def _refresh_status(self):
        if config.is_spotify_connected():
            self.status_lbl.configure(
                text="✓  Conectado ao Spotify", text_color=GREEN
            )
        elif config.get_spotify_client_id():
            self.status_lbl.configure(
                text="•  Client ID salvo, falta conectar", text_color=YELLOW
            )
        else:
            self.status_lbl.configure(
                text="✗  Nenhum Client ID configurado", text_color=TEXT_SUB
            )

    def _connect(self):
        cid = self.id_entry.get().strip()
        if not cid:
            messagebox.showwarning(
                "Atenção", "Preencha o Client ID antes de conectar.", parent=self
            )
            return
        try:
            config.set_spotify_client_id(cid)
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível salvar Client ID: {e}", parent=self)
            return

        self.connect_btn.configure(state="disabled", text="Aguardando navegador…")
        threading.Thread(target=self._connect_worker, args=(cid,), daemon=True).start()

    def _connect_worker(self, client_id: str):
        def status_cb(msg: str):
            self.after(0, lambda: self.connect_btn.configure(text=msg))

        try:
            tokens = spotify_auth.perform_login(client_id, on_status=status_cb)
        except spotify_auth.SpotifyAuthError as e:
            err = str(e)
            self.after(0, lambda: self._on_connect_error(err))
            return
        except Exception as e:
            err = repr(e)
            self.after(0, lambda: self._on_connect_error(err))
            return

        access = tokens.get("access_token")
        refresh = tokens.get("refresh_token")
        expires_at = time.time() + int(tokens.get("expires_in", 3600))
        if not access or not refresh:
            self.after(0, lambda: self._on_connect_error(
                "Resposta do Spotify sem tokens completos."
            ))
            return
        try:
            config.set_spotify_tokens(access, refresh, expires_at)
        except Exception as e:
            err = str(e)
            self.after(0, lambda: self._on_connect_error(f"Falha ao salvar tokens: {err}"))
            return
        self.after(0, self._on_connect_done)

    def _on_connect_done(self):
        self.connect_btn.configure(state="normal", text="🔗  Conectar com Spotify")
        self._refresh_status()
        messagebox.showinfo(
            "Spotify", "Conectado com sucesso!", parent=self
        )

    def _on_connect_error(self, msg: str):
        self.connect_btn.configure(state="normal", text="🔗  Conectar com Spotify")
        self._refresh_status()
        messagebox.showerror("Falha ao conectar", msg, parent=self)

    def _disconnect(self):
        if not messagebox.askyesno(
            "Confirmar",
            "Remover Client ID e tokens do Spotify deste computador?",
            parent=self,
        ):
            return
        try:
            config.clear_spotify_credentials()
        except Exception:
            pass
        self.id_entry.delete(0, "end")
        self._refresh_status()


# ── Track row widget ───────────────────────────────────────────────────────────
class TrackRow(ctk.CTkFrame):
    def __init__(self, master, index: int, entry: dict, already_downloaded: bool = False, **kwargs):
        super().__init__(master, fg_color=BG_ITEM, corner_radius=8, **kwargs)
        self.entry = entry
        self.index = index
        self.already_downloaded = already_downloaded
        self.var = tk.BooleanVar(value=not already_downloaded)

        self.grid_columnconfigure(2, weight=1)

        self.chk = ctk.CTkCheckBox(
            self, variable=self.var, text="", width=24,
            fg_color=ACCENT, hover_color="#DC2626", border_color="#555555"
        )
        self.chk.grid(row=0, column=0, padx=(8, 4), pady=8)

        ctk.CTkLabel(self, text=f"{index + 1:02d}", text_color=TEXT_SUB,
                     font=("Inter", 11), width=28).grid(row=0, column=1, padx=4)

        title = entry.get("title", "Sem título")
        self.title_lbl = ctk.CTkLabel(
            self, text=title, text_color=TEXT_MAIN,
            font=("Inter", 12), anchor="w", wraplength=400
        )
        self.title_lbl.grid(row=0, column=2, padx=8, sticky="ew")

        dur = YoutubeDownloader.format_duration(entry.get("duration"))
        ctk.CTkLabel(self, text=dur, text_color=TEXT_SUB,
                     font=("Inter", 11), width=48).grid(row=0, column=3, padx=8)

        self.status_lbl = ctk.CTkLabel(
            self, text="", text_color=TEXT_SUB,
            font=("Inter", 10, "bold"), width=110
        )
        self.status_lbl.grid(row=0, column=4, padx=(0, 10))

        if already_downloaded:
            self.set_status("↻ Já baixado", TEXT_SUB)
        elif entry.get("_spotify_origin"):
            self.set_status("🎵 via Spotify", "#1DB954")

    def set_status(self, text: str, color: str = TEXT_SUB):
        self.status_lbl.configure(text=text, text_color=color)

    def set_downloading(self):
        self.configure(fg_color="#1e2a3a")
        self.set_status("⬇ Baixando", "#60A5FA")

    def set_done(self):
        self.configure(fg_color="#12271e")
        self.set_status("✓ Concluído", GREEN)

    def set_error(self):
        self.configure(fg_color="#2a1212")
        self.set_status("✗ Erro", ACCENT)

    @property
    def selected(self) -> bool:
        return self.var.get()


# ── Main Window ────────────────────────────────────────────────────────────────
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("BaixaTrack")
        self.geometry("820x700")
        self.minsize(720, 580)
        self.configure(fg_color=BG_DARK)
        self._apply_window_icon()

        self.downloader = YoutubeDownloader()
        self._entries: list = []
        self._track_rows: list = []
        self._is_downloading = False
        self._thumb_ref = None
        self._build_gen = 0
        self._fetch_cancel: threading.Event | None = None

        self._build_ui()
        # Check FFmpeg 300ms after window appears (non-blocking)
        self.after(300, self._check_ffmpeg)

    def _apply_window_icon(self):
        ico_path = resource_path(os.path.join("assets", "logo.ico"))
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(default=ico_path)
            except tk.TclError:
                pass

    # ── FFmpeg check ───────────────────────────────────────────────────────────
    def _check_ffmpeg(self):
        if not ffmpeg_manager.is_ffmpeg_available():
            FFmpegSetupDialog(self, on_complete=lambda: None)

    # ── UI Construction ────────────────────────────────────────────────────────
    def _build_ui(self):
        self.grid_rowconfigure(4, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Header ──
        header = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=0, height=64)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header, text="▶  YouTube MP3 Extractor",
            font=("Inter", 20, "bold"), text_color=ACCENT
        ).grid(row=0, column=0, padx=20, pady=16)

        ctk.CTkButton(
            header, text="⚙  Configurações", width=140, height=32,
            font=("Inter", 12), fg_color=BG_ITEM, hover_color="#333333",
            text_color=TEXT_MAIN,
            command=self._open_settings
        ).grid(row=0, column=2, padx=20, pady=16, sticky="e")

        # ── URL bar ──
        url_frame = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12)
        url_frame.grid(row=1, column=0, padx=16, pady=(12, 6), sticky="ew")
        url_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(url_frame, text="URL do Vídeo ou Playlist:",
                     font=("Inter", 12, "bold"), text_color=TEXT_SUB
                     ).grid(row=0, column=0, columnspan=2, padx=16, pady=(12, 4), sticky="w")

        self.url_entry = ctk.CTkEntry(
            url_frame, placeholder_text="YouTube (vídeo/playlist) ou Spotify (playlist pública)",
            font=("Inter", 13), height=42,
            fg_color=BG_ITEM, border_color="#333333", text_color=TEXT_MAIN
        )
        self.url_entry.grid(row=1, column=0, padx=(16, 8), pady=(0, 12), sticky="ew")
        self.url_entry.bind("<Return>", lambda e: self._on_fetch())

        self.fetch_btn = ctk.CTkButton(
            url_frame, text="Buscar", width=100, height=42,
            font=("Inter", 13, "bold"),
            fg_color=ACCENT, hover_color="#DC2626",
            command=self._on_fetch
        )
        self.fetch_btn.grid(row=1, column=1, padx=(0, 8), pady=(0, 12))

        self.clear_btn = ctk.CTkButton(
            url_frame, text="Limpar", width=90, height=42,
            font=("Inter", 13),
            fg_color=BG_ITEM, hover_color="#333333", text_color=TEXT_MAIN,
            command=self._clear_selection
        )
        self.clear_btn.grid(row=1, column=2, padx=(0, 16), pady=(0, 12))

        # ── Info card ──
        self.info_frame = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12)
        self.info_frame.grid(row=2, column=0, padx=16, pady=6, sticky="ew")
        self.info_frame.grid_columnconfigure(1, weight=1)
        self.info_frame.grid_remove()

        self.thumb_lbl = ctk.CTkLabel(self.info_frame, text="")
        self.thumb_lbl.grid(row=0, column=0, padx=16, pady=12, sticky="nw")

        info_text = ctk.CTkFrame(self.info_frame, fg_color="transparent")
        info_text.grid(row=0, column=1, padx=8, pady=12, sticky="ew")
        info_text.grid_columnconfigure(0, weight=1)

        self.info_title = ctk.CTkLabel(
            info_text, text="", font=("Inter", 14, "bold"),
            text_color=TEXT_MAIN, anchor="w", wraplength=550
        )
        self.info_title.grid(row=0, column=0, sticky="ew")

        self.info_sub = ctk.CTkLabel(
            info_text, text="", font=("Inter", 12),
            text_color=TEXT_SUB, anchor="w"
        )
        self.info_sub.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        sel_frame = ctk.CTkFrame(info_text, fg_color="transparent")
        sel_frame.grid(row=2, column=0, sticky="w", pady=(8, 0))

        ctk.CTkButton(
            sel_frame, text="Selecionar Todos", width=130, height=28,
            font=("Inter", 11), fg_color="#333333", hover_color="#444444",
            command=self._select_all
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            sel_frame, text="Desmarcar Todos", width=130, height=28,
            font=("Inter", 11), fg_color="#333333", hover_color="#444444",
            command=self._deselect_all
        ).pack(side="left")

        self.include_downloaded_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            sel_frame, text="Incluir vídeos já baixados anteriormente",
            variable=self.include_downloaded_var,
            font=("Inter", 11), text_color=TEXT_SUB,
            fg_color=ACCENT, hover_color="#DC2626", border_color="#555555",
            command=self._on_toggle_include_downloaded,
        ).pack(side="left", padx=(16, 0))

        # ── Track list ──
        list_outer = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12)
        list_outer.grid(row=4, column=0, padx=16, pady=6, sticky="nsew")
        list_outer.grid_rowconfigure(0, weight=1)
        list_outer.grid_columnconfigure(0, weight=1)

        self.track_scroll = ctk.CTkScrollableFrame(
            list_outer, fg_color="transparent", label_text=""
        )
        self.track_scroll.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")
        self.track_scroll.grid_columnconfigure(0, weight=1)

        self.empty_lbl = ctk.CTkLabel(
            self.track_scroll,
            text='Cole um link de vídeo ou playlist acima e clique em "Buscar".',
            text_color=TEXT_SUB, font=("Inter", 13)
        )
        self.empty_lbl.grid(row=0, column=0, pady=40)

        # ── Bottom bar ──
        bottom = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=0)
        bottom.grid(row=5, column=0, sticky="ew")
        bottom.grid_columnconfigure(1, weight=1)

        folder_frame = ctk.CTkFrame(bottom, fg_color="transparent")
        folder_frame.grid(row=0, column=0, columnspan=3, padx=16, pady=(10, 4), sticky="ew")
        folder_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(folder_frame, text="Salvar em:", font=("Inter", 12),
                     text_color=TEXT_SUB, width=70).grid(row=0, column=0, sticky="w")

        self.folder_var = tk.StringVar(value=os.path.expanduser("~/Music"))
        self.folder_entry = ctk.CTkEntry(
            folder_frame, textvariable=self.folder_var,
            font=("Inter", 12), height=34,
            fg_color=BG_ITEM, border_color="#333333", text_color=TEXT_MAIN
        )
        self.folder_entry.grid(row=0, column=1, padx=8, sticky="ew")

        ctk.CTkButton(
            folder_frame, text="📁", width=36, height=34,
            fg_color=BG_ITEM, hover_color="#333333", font=("Inter", 14),
            command=self._choose_folder
        ).grid(row=0, column=2)

        self.progress_bar = ctk.CTkProgressBar(
            bottom, fg_color=BG_ITEM, progress_color=ACCENT, height=6
        )
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, columnspan=3, padx=16, pady=(4, 0), sticky="ew")

        self.status_var = tk.StringVar(value="Pronto")
        self.status_lbl = ctk.CTkLabel(
            bottom, textvariable=self.status_var,
            font=("Inter", 11), text_color=TEXT_SUB, anchor="w"
        )
        self.status_lbl.grid(row=2, column=0, columnspan=2, padx=16, pady=(2, 4), sticky="ew")

        self.dl_btn = ctk.CTkButton(
            bottom, text="⬇  Baixar MP3", height=44,
            font=("Inter", 14, "bold"),
            fg_color=GREEN, hover_color="#16A34A",
            state="disabled",
            command=self._on_download
        )
        self.dl_btn.grid(row=2, column=2, padx=16, pady=(2, 12))

    # ── Fetch ──────────────────────────────────────────────────────────────────
    def _on_fetch(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Atenção", "Digite uma URL do YouTube ou Spotify.")
            return

        if spotify.is_spotify_url(url):
            if not config.is_spotify_connected():
                messagebox.showwarning(
                    "Spotify não conectado",
                    "Conecte sua conta do Spotify em ⚙ Configurações primeiro."
                )
                self._open_settings()
                return
            cancel_event = threading.Event()
            self._enter_fetch_mode(cancel_event)
            self._set_status("Lendo playlist do Spotify…", YELLOW)
            threading.Thread(
                target=self._fetch_spotify_worker,
                args=(url, cancel_event),
                daemon=True,
            ).start()
            return

        self.fetch_btn.configure(state="disabled", text="Buscando…")
        self._set_status("Obtendo informações…", YELLOW)
        threading.Thread(target=self._fetch_worker, args=(url,), daemon=True).start()

    # ── Cancellable Spotify fetch UI ───────────────────────────────────────────
    def _enter_fetch_mode(self, cancel_event: threading.Event):
        self._fetch_cancel = cancel_event
        self.fetch_btn.configure(
            state="normal", text="✕ Cancelar",
            fg_color=BG_ITEM, hover_color="#333333",
            command=self._on_fetch_cancel,
        )

    def _exit_fetch_mode(self):
        self._fetch_cancel = None
        self.fetch_btn.configure(
            state="normal", text="Buscar",
            fg_color=ACCENT, hover_color="#DC2626",
            command=self._on_fetch,
        )

    def _on_fetch_cancel(self):
        if self._fetch_cancel:
            self._fetch_cancel.set()
            self.fetch_btn.configure(state="disabled", text="Cancelando…")
            self._set_status("Cancelando…", YELLOW)

    def _fetch_worker(self, url: str):
        try:
            info = self.downloader.get_info(url)
            self.after(0, lambda: self._on_fetch_done(info))
        except Exception as e:
            msg = str(e) or repr(e)
            traceback.print_exc()
            self.after(0, lambda m=msg: self._on_fetch_error(m))

    def _fetch_spotify_worker(self, url: str, cancel_event: threading.Event):
        # Throttled status updater — coalesces rapid callbacks into at most one
        # GUI update every ~200ms (or every 25 items) so the Tk event queue
        # stays responsive on multi-thousand-track playlists.
        page_state = {"ts": 0.0}
        def on_page(loaded, total):
            now = time.time()
            if loaded == total or (now - page_state["ts"]) > 0.2:
                page_state["ts"] = now
                self.after(0, lambda l=loaded, t=total: self._set_status(
                    f"Lendo playlist do Spotify… {l}/{t}", YELLOW
                ))

        try:
            playlist = spotify.fetch_playlist(url, on_page=on_page, cancel_event=cancel_event)
        except spotify.SpotifyError as e:
            msg = str(e) or repr(e)
            traceback.print_exc()
            self.after(0, lambda m=msg: self._on_fetch_error(m))
            return
        except Exception as e:
            msg = f"Erro inesperado ao buscar playlist: {e!r}"
            traceback.print_exc()
            self.after(0, lambda m=msg: self._on_fetch_error(m))
            return

        if cancel_event.is_set():
            self.after(0, self._on_fetch_cancelled)
            return

        tracks = playlist["tracks"]
        if not tracks:
            self.after(0, lambda: self._on_fetch_error("Playlist do Spotify vazia."))
            return

        total = len(tracks)
        self.after(0, lambda: self._set_status(
            f"Buscando 0/{total} no YouTube…", "#60A5FA"
        ))

        prog_state = {"done": 0, "ts": 0.0}
        def on_prog(done, tot, label):
            now = time.time()
            if done == tot or done - prog_state["done"] >= 25 or (now - prog_state["ts"]) > 0.2:
                prog_state["done"] = done
                prog_state["ts"] = now
                self.after(0, lambda d=done, tt=tot, l=label: self._set_status(
                    f"Buscando {d}/{tt} no YouTube… ({l})", "#60A5FA"
                ))

        try:
            entries = spotify.search_youtube_for_tracks(
                tracks, on_progress=on_prog, cancel_event=cancel_event,
            )
        except Exception as e:
            msg = f"Erro na busca do YouTube: {e!r}"
            traceback.print_exc()
            self.after(0, lambda m=msg: self._on_fetch_error(m))
            return

        if cancel_event.is_set():
            self.after(0, self._on_fetch_cancelled)
            return

        if not entries:
            self.after(0, lambda: self._on_fetch_error(
                "Nenhuma faixa correspondente encontrada no YouTube."
            ))
            return

        info = {
            "type": "playlist",
            "title": f"🎵 {playlist['name']} (via Spotify)",
            "entries": entries,
        }
        self.after(0, lambda: self._on_fetch_done(info))

    def _on_fetch_done(self, info: dict):
        self._exit_fetch_mode()
        self._entries = info["entries"]

        self.info_title.configure(text=info["title"])
        n = len(self._entries)
        kind = "playlist" if info["type"] == "playlist" else "vídeo único"
        self.info_sub.configure(text=f"{kind} · {n} faixa{'s' if n != 1 else ''}")
        self.info_frame.grid()

        if self._entries:
            thumb_url = self._entries[0].get("thumbnail", "")
            if thumb_url:
                threading.Thread(target=self._load_thumb, args=(thumb_url,), daemon=True).start()

        plural = 's' if n != 1 else ''
        def _done():
            self.dl_btn.configure(state="normal")
            self._set_status(f"{n} faixa{plural} encontrada{plural}.", GREEN)
        self._build_track_list(on_complete=_done)

    def _on_fetch_error(self, msg):
        if not msg:
            msg = "Erro desconhecido (veja o terminal para detalhes)."
        msg = str(msg)
        self._exit_fetch_mode()
        self._set_status(f"Erro: {msg}", ACCENT)
        messagebox.showerror("Erro ao buscar", msg)

    def _on_fetch_cancelled(self):
        self._exit_fetch_mode()
        self._set_status("Busca cancelada.", TEXT_SUB)

    def _load_thumb(self, url: str):
        photo = load_thumbnail(url, (80, 60))
        if photo:
            self.after(0, lambda: self.thumb_lbl.configure(image=photo, text=""))
            self._thumb_ref = photo

    def _build_track_list(self, on_complete=None):
        # Bumping the generation invalidates any batch still scheduled via after().
        self._build_gen += 1
        for row in self._track_rows:
            row.destroy()
        self._track_rows.clear()
        self.empty_lbl.grid_remove()
        self.track_scroll.grid_columnconfigure(0, weight=1)

        if not self._entries:
            if on_complete:
                on_complete()
            return

        self._build_track_list_batch(0, self._build_gen, on_complete)

    def _build_track_list_batch(self, start: int, gen: int, on_complete, batch_size: int = 40):
        # A newer fetch (or a clear) has bumped the generation — drop this batch.
        if gen != self._build_gen:
            return
        include_dl = self.include_downloaded_var.get()
        n = len(self._entries)
        end = min(start + batch_size, n)
        for i in range(start, end):
            entry = self._entries[i]
            already = history.is_downloaded(entry.get("id", ""))
            row = TrackRow(
                self.track_scroll, index=i, entry=entry,
                already_downloaded=already and not include_dl,
            )
            if already and include_dl:
                row.set_status("↻ Já baixado", TEXT_SUB)
            row.grid(row=i, column=0, padx=4, pady=3, sticky="ew")
            self._track_rows.append(row)
        if end < n:
            self._set_status(f"Montando lista… {end}/{n}", "#60A5FA")
            self.after(1, lambda: self._build_track_list_batch(end, gen, on_complete, batch_size))
        elif on_complete:
            on_complete()

    def _on_toggle_include_downloaded(self):
        """Re-apply selection rules when toggle flips, without rebuilding the list."""
        include_dl = self.include_downloaded_var.get()
        for row in self._track_rows:
            vid = row.entry.get("id", "")
            if history.is_downloaded(vid):
                row.var.set(include_dl)

    # ── Download ───────────────────────────────────────────────────────────────
    def _on_download(self):
        selected = [(row.index, row.entry) for row in self._track_rows if row.selected]
        if not selected:
            messagebox.showwarning("Atenção", "Nenhuma faixa selecionada.")
            return

        out_dir = self.folder_var.get().strip()
        if not out_dir:
            messagebox.showwarning("Atenção", "Escolha uma pasta de destino.")
            return

        os.makedirs(out_dir, exist_ok=True)
        self._is_downloading = True
        self.dl_btn.configure(state="disabled", text="Baixando…")
        self.fetch_btn.configure(state="disabled")
        self.progress_bar.set(0)

        entries = [e for _, e in selected]
        threading.Thread(target=self._download_worker, args=(entries, out_dir), daemon=True).start()

    def _download_worker(self, entries: list, out_dir: str):
        total = len(entries)
        done_count = 0

        def on_entry_start(idx, total, title):
            self.after(0, lambda: self._track_rows[idx].set_downloading())
            self.after(0, lambda: self._set_status(f"Baixando: {title}", "#60A5FA"))

        def on_progress(idx, total, pct, speed, eta):
            overall = (done_count + pct / 100) / total
            self.after(0, lambda: self.progress_bar.set(overall))
            parts = [f"[{idx+1}/{total}] {pct:.0f}%"]
            if speed: parts.append(speed)
            if eta:   parts.append(f"ETA {eta}")
            self.after(0, lambda: self._set_status(" · ".join(parts), "#60A5FA"))

        def on_entry_done(idx, total, title, folder):
            nonlocal done_count
            done_count += 1
            entry = self._track_rows[idx].entry
            try:
                history.mark_downloaded(entry.get("id", ""), title, folder)
            except Exception:
                pass
            self.after(0, lambda: self._track_rows[idx].set_done())
            self.after(0, lambda: self.progress_bar.set(done_count / total))

        def on_error(idx, title, msg):
            self.after(0, lambda: self._track_rows[idx].set_error())
            self.after(0, lambda: self._set_status(f"Erro em '{title}': {msg}", ACCENT))

        self.downloader.download_entries(
            entries, out_dir,
            on_progress=on_progress,
            on_entry_start=on_entry_start,
            on_entry_done=on_entry_done,
            on_error=on_error,
        )
        self.after(0, self._on_download_finished, done_count, total, out_dir)

    def _on_download_finished(self, done: int, total: int, out_dir: str):
        self._is_downloading = False
        self.dl_btn.configure(state="normal", text="⬇  Baixar MP3")
        self.fetch_btn.configure(state="normal")
        self.progress_bar.set(1)
        self._set_status(
            f"✓ Concluído! {done}/{total} faixa{'s' if total != 1 else ''} "
            f"baixada{'s' if total != 1 else ''} em: {out_dir}",
            GREEN
        )
        if done > 0 and messagebox.askyesno(
            "Download concluído",
            f"{done} faixa{'s' if done != 1 else ''} salva{'s' if done != 1 else ''} em:\n{out_dir}\n\nAbrir pasta?"
        ):
            os.startfile(out_dir)

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _open_settings(self):
        SettingsDialog(self)

    def _choose_folder(self):
        folder = filedialog.askdirectory(initialdir=self.folder_var.get())
        if folder:
            self.folder_var.set(folder)

    def _clear_selection(self):
        if self._is_downloading:
            messagebox.showwarning("Atenção", "Aguarde o download terminar antes de limpar.")
            return
        self.url_entry.delete(0, "end")
        # Invalidate any in-flight batch builder so its leftover after() calls bail out.
        self._build_gen += 1
        for row in self._track_rows:
            row.destroy()
        self._track_rows.clear()
        self._entries = []
        self.info_frame.grid_remove()
        self.info_title.configure(text="")
        self.info_sub.configure(text="")
        self.thumb_lbl.configure(image="", text="")
        self._thumb_ref = None
        self.empty_lbl.grid(row=0, column=0, pady=40)
        self.dl_btn.configure(state="disabled")
        self.progress_bar.set(0)
        self._set_status("Pronto")

    def _select_all(self):
        for row in self._track_rows:
            row.var.set(True)

    def _deselect_all(self):
        for row in self._track_rows:
            row.var.set(False)

    def _set_status(self, msg: str, color: str = TEXT_SUB):
        self.status_var.set(msg)
        self.status_lbl.configure(text_color=color)

    def on_close(self):
        if self._is_downloading:
            if messagebox.askyesno("Sair", "Um download está em andamento. Deseja cancelar e sair?"):
                self.downloader.cancel()
                self.destroy()
        else:
            self.destroy()


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
