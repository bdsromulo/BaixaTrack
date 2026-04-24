"""
app.py - Main GUI application for YouTube MP3 Extractor
Built with customtkinter for a modern dark-mode interface.
Compatible with PyInstaller (sys._MEIPASS resource paths).
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageTk
import requests
from io import BytesIO

from downloader import YoutubeDownloader, DownloadError
import ffmpeg_manager

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


# ── Track row widget ───────────────────────────────────────────────────────────
class TrackRow(ctk.CTkFrame):
    def __init__(self, master, index: int, entry: dict, **kwargs):
        super().__init__(master, fg_color=BG_ITEM, corner_radius=8, **kwargs)
        self.entry = entry
        self.index = index
        self.var = tk.BooleanVar(value=True)

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
            font=("Inter", 10, "bold"), width=70
        )
        self.status_lbl.grid(row=0, column=4, padx=(0, 10))

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
        self.title("YouTube MP3 Extractor")
        self.geometry("820x700")
        self.minsize(720, 580)
        self.configure(fg_color=BG_DARK)

        self.downloader = YoutubeDownloader()
        self._entries: list = []
        self._track_rows: list = []
        self._is_downloading = False
        self._thumb_ref = None

        self._build_ui()
        # Check FFmpeg 300ms after window appears (non-blocking)
        self.after(300, self._check_ffmpeg)

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

        # ── URL bar ──
        url_frame = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=12)
        url_frame.grid(row=1, column=0, padx=16, pady=(12, 6), sticky="ew")
        url_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(url_frame, text="URL do Vídeo ou Playlist:",
                     font=("Inter", 12, "bold"), text_color=TEXT_SUB
                     ).grid(row=0, column=0, columnspan=2, padx=16, pady=(12, 4), sticky="w")

        self.url_entry = ctk.CTkEntry(
            url_frame, placeholder_text="https://www.youtube.com/watch?v=... ou playlist",
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
        self.fetch_btn.grid(row=1, column=1, padx=(0, 16), pady=(0, 12))

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
            messagebox.showwarning("Atenção", "Digite uma URL do YouTube.")
            return
        self.fetch_btn.configure(state="disabled", text="Buscando…")
        self._set_status("Obtendo informações…", YELLOW)
        threading.Thread(target=self._fetch_worker, args=(url,), daemon=True).start()

    def _fetch_worker(self, url: str):
        try:
            info = self.downloader.get_info(url)
            self.after(0, lambda: self._on_fetch_done(info))
        except Exception as e:
            self.after(0, lambda: self._on_fetch_error(str(e)))

    def _on_fetch_done(self, info: dict):
        self.fetch_btn.configure(state="normal", text="Buscar")
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

        self._build_track_list()
        self.dl_btn.configure(state="normal")
        self._set_status(f"{n} faixa{'s' if n != 1 else ''} encontrada{'s' if n != 1 else ''}.", GREEN)

    def _on_fetch_error(self, msg: str):
        self.fetch_btn.configure(state="normal", text="Buscar")
        self._set_status(f"Erro: {msg}", ACCENT)
        messagebox.showerror("Erro ao buscar", msg)

    def _load_thumb(self, url: str):
        photo = load_thumbnail(url, (80, 60))
        if photo:
            self.after(0, lambda: self.thumb_lbl.configure(image=photo, text=""))
            self._thumb_ref = photo

    def _build_track_list(self):
        for row in self._track_rows:
            row.destroy()
        self._track_rows.clear()
        self.empty_lbl.grid_remove()

        for i, entry in enumerate(self._entries):
            row = TrackRow(self.track_scroll, index=i, entry=entry)
            row.grid(row=i, column=0, padx=4, pady=3, sticky="ew")
            self.track_scroll.grid_columnconfigure(0, weight=1)
            self._track_rows.append(row)

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
    def _choose_folder(self):
        folder = filedialog.askdirectory(initialdir=self.folder_var.get())
        if folder:
            self.folder_var.set(folder)

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
