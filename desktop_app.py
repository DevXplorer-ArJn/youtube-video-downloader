import os
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import yt_dlp
from imageio_ffmpeg import get_ffmpeg_exe
from yt_dlp.postprocessor import PostProcessor


DOWNLOAD_DIR = Path.home() / "Downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


def yt_dlp_options():
    return {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "ffmpeg_location": get_ffmpeg_exe(),
        "windowsfilenames": True,
        "socket_timeout": 30,
    }


def format_size(bytes_value):
    if not bytes_value:
        return None
    size = float(bytes_value)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024
    return None


class H264AacMp4PostProcessor(PostProcessor):
    @staticmethod
    def select_encoder():
        ffmpeg = get_ffmpeg_exe()
        probe = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "color=size=160x90:rate=1",
                "-t",
                "1",
                "-an",
                "-c:v",
                "h264_mf",
                "-f",
                "null",
                "-",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if probe.returncode == 0:
            return "h264_mf"
        return "libx264"

    def run(self, info):
        filepath = Path(info["filepath"])
        temp_filepath = filepath.with_name(filepath.stem + ".h264-aac.tmp.mp4")
        encoder = self.select_encoder()
        video_args = ["-c:v", encoder]
        if encoder == "libx264":
            video_args.extend(["-preset", "veryfast", "-crf", "18"])
        else:
            video_args.extend(["-b:v", "8M"])

        command = [
            get_ffmpeg_exe(),
            "-y",
            "-i",
            str(filepath),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            *video_args,
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(temp_filepath),
        ]

        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            if temp_filepath.exists():
                temp_filepath.unlink()
            raise yt_dlp.utils.DownloadError(
                "FFmpeg could not convert the video to H.264/AAC MP4."
            )

        temp_filepath.replace(filepath)
        return [], info


class VideoDownloaderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Video Downloader")
        self.geometry("960x700")
        self.minsize(780, 620)

        self.current_qualities = []
        self.selected_height = None
        self.download_thread = None

        self.colors = {
            "background": "#F4F6FA",
            "surface": "#FFFFFF",
            "sidebar": "#17233B",
            "sidebar_muted": "#9BA9C2",
            "text": "#17233B",
            "muted": "#718096",
            "border": "#E4E9F1",
            "accent": "#536DFE",
            "accent_hover": "#4058E8",
            "accent_soft": "#EEF0FF",
        }
        self.configure(bg=self.colors["background"])
        self.setup_styles()
        self.build_layout()

    def setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "App.TFrame",
            background=self.colors["background"],
        )
        style.configure(
            "Card.TFrame",
            background=self.colors["surface"],
        )
        style.configure(
            "Title.TLabel",
            background=self.colors["background"],
            foreground=self.colors["text"],
            font=("Segoe UI", 22, "bold"),
        )
        style.configure(
            "Subtitle.TLabel",
            background=self.colors["background"],
            foreground=self.colors["muted"],
            font=("Segoe UI", 10),
        )
        style.configure(
            "Section.TLabel",
            background=self.colors["surface"],
            foreground=self.colors["text"],
            font=("Segoe UI", 11, "bold"),
        )
        style.configure(
            "Body.TLabel",
            background=self.colors["surface"],
            foreground=self.colors["muted"],
            font=("Segoe UI", 9),
        )
        style.configure(
            "VideoTitle.TLabel",
            background=self.colors["surface"],
            foreground=self.colors["text"],
            font=("Segoe UI", 13, "bold"),
        )
        style.configure(
            "Status.TLabel",
            background=self.colors["surface"],
            foreground=self.colors["muted"],
            font=("Segoe UI", 9),
        )
        style.configure(
            "Url.TEntry",
            fieldbackground="#F8F9FC",
            foreground=self.colors["text"],
            insertcolor=self.colors["text"],
            padding=(12, 11),
            bordercolor=self.colors["border"],
            lightcolor=self.colors["border"],
            darkcolor=self.colors["border"],
            font=("Segoe UI", 10),
        )
        style.configure(
            "Primary.TButton",
            background=self.colors["accent"],
            foreground="#FFFFFF",
            padding=(18, 11),
            borderwidth=0,
            font=("Segoe UI", 9, "bold"),
        )
        style.map(
            "Primary.TButton",
            background=[("disabled", "#AEB8F8"), ("active", self.colors["accent_hover"])],
            foreground=[("disabled", "#FFFFFF")],
        )
        style.configure(
            "Secondary.TButton",
            background=self.colors["surface"],
            foreground=self.colors["text"],
            padding=(12, 8),
            borderwidth=1,
            relief="solid",
            bordercolor=self.colors["border"],
            font=("Segoe UI", 9, "bold"),
        )
        style.map(
            "Secondary.TButton",
            background=[("active", "#F5F7FB")],
        )
        style.configure(
            "Quality.TButton",
            background=self.colors["surface"],
            foreground=self.colors["text"],
            padding=(14, 11),
            borderwidth=1,
            relief="solid",
            bordercolor=self.colors["border"],
            font=("Segoe UI", 9, "bold"),
        )
        style.map("Quality.TButton", background=[("active", "#F5F7FB")])
        style.configure(
            "SelectedQuality.TButton",
            background=self.colors["accent_soft"],
            foreground=self.colors["accent"],
            padding=(14, 11),
            borderwidth=1,
            relief="solid",
            bordercolor=self.colors["accent"],
            font=("Segoe UI", 9, "bold"),
        )
        style.configure(
            "Horizontal.TProgressbar",
            background=self.colors["accent"],
            troughcolor="#E9EDF5",
            borderwidth=0,
            thickness=8,
        )

    def build_layout(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        sidebar = tk.Frame(self, bg=self.colors["sidebar"], width=220)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)

        brand = tk.Frame(sidebar, bg=self.colors["sidebar"])
        brand.grid(row=0, column=0, sticky="ew", padx=22, pady=(28, 38))
        tk.Label(
            brand,
            text="▶",
            bg="#34456B",
            fg="#FFFFFF",
            font=("Segoe UI", 12, "bold"),
            width=3,
            height=1,
            pady=6,
        ).pack(side="left")
        tk.Label(
            brand,
            text="  Video\n  Downloader",
            bg=self.colors["sidebar"],
            fg="#FFFFFF",
            justify="left",
            font=("Segoe UI", 11, "bold"),
        ).pack(side="left")

        tk.Label(
            sidebar,
            text="WORKSPACE",
            bg=self.colors["sidebar"],
            fg=self.colors["sidebar_muted"],
            font=("Segoe UI", 8, "bold"),
        ).grid(row=1, column=0, sticky="w", padx=24, pady=(0, 10))
        tk.Label(
            sidebar,
            text="  ↓   Download video",
            bg="#283754",
            fg="#FFFFFF",
            anchor="w",
            padx=14,
            pady=12,
            font=("Segoe UI", 9, "bold"),
        ).grid(row=2, column=0, sticky="ew", padx=12)

        tk.Frame(sidebar, bg="#34425C", height=1).grid(
            row=3, column=0, sticky="ew", padx=22, pady=24
        )
        tk.Label(
            sidebar,
            text="READY WHEN YOU ARE",
            bg=self.colors["sidebar"],
            fg=self.colors["sidebar_muted"],
            font=("Segoe UI", 8, "bold"),
        ).grid(row=4, column=0, sticky="w", padx=24, pady=(0, 8))
        tk.Label(
            sidebar,
            text="Choose a video link to\nsee available qualities.",
            bg=self.colors["sidebar"],
            fg="#FFFFFF",
            justify="left",
            font=("Segoe UI", 9),
        ).grid(row=5, column=0, sticky="w", padx=24)
        tk.Label(
            sidebar,
            text="MP4  ·  H.264 + AAC",
            bg=self.colors["sidebar"],
            fg=self.colors["sidebar_muted"],
            font=("Segoe UI", 8),
        ).grid(row=6, column=0, sticky="sw", padx=24, pady=22)

        content = ttk.Frame(self, style="App.TFrame", padding=(34, 30, 34, 28))
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(3, weight=1)

        ttk.Label(content, text="Download a video", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            content,
            text="Paste a YouTube link and pick the quality that works for you.",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(5, 22))

        link_card = ttk.Frame(content, style="Card.TFrame", padding=20)
        link_card.grid(row=2, column=0, sticky="ew", pady=(0, 16))
        link_card.grid_columnconfigure(0, weight=1)
        ttk.Label(link_card, text="VIDEO LINK", style="Section.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )
        url_row = ttk.Frame(link_card, style="Card.TFrame")
        url_row.grid(row=1, column=0, sticky="ew")
        url_row.grid_columnconfigure(0, weight=1)
        self.url_entry = ttk.Entry(url_row, style="Url.TEntry")
        self.url_entry.grid(row=0, column=0, sticky="ew")
        self.url_entry.bind("<Return>", lambda _event: self.lookup())
        self.lookup_button = ttk.Button(
            url_row,
            text="Find qualities",
            style="Primary.TButton",
            command=self.lookup,
        )
        self.lookup_button.grid(row=0, column=1, padx=(10, 0))

        download_card = ttk.Frame(content, style="Card.TFrame", padding=20)
        download_card.grid(row=3, column=0, sticky="nsew")
        download_card.grid_columnconfigure(0, weight=1)
        download_card.grid_rowconfigure(5, weight=1)

        ttk.Label(download_card, text="VIDEO DETAILS", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.video_title = ttk.Label(
            download_card,
            text="Your video details will appear here",
            style="VideoTitle.TLabel",
        )
        self.video_title.grid(row=1, column=0, sticky="w", pady=(16, 3))
        self.video_meta = ttk.Label(
            download_card,
            text="Add a link above to get started.",
            style="Body.TLabel",
        )
        self.video_meta.grid(row=2, column=0, sticky="w")

        ttk.Separator(download_card).grid(
            row=3, column=0, sticky="ew", pady=(18, 16)
        )
        quality_header = ttk.Frame(download_card, style="Card.TFrame")
        quality_header.grid(row=4, column=0, sticky="ew")
        ttk.Label(
            quality_header,
            text="Choose quality",
            style="Section.TLabel",
        ).pack(side="left")
        ttk.Label(
            quality_header,
            text="Downloads are saved as MP4",
            style="Body.TLabel",
        ).pack(side="right")

        self.quality_frame = ttk.Frame(download_card, style="Card.TFrame")
        self.quality_frame.grid(row=5, column=0, sticky="ew", pady=(12, 8))
        for column in range(4):
            self.quality_frame.grid_columnconfigure(column, weight=1, uniform="quality")

        ttk.Separator(download_card).grid(
            row=6, column=0, sticky="ew", pady=(12, 14)
        )
        status_row = ttk.Frame(download_card, style="Card.TFrame")
        status_row.grid(row=7, column=0, sticky="ew")
        status_row.grid_columnconfigure(0, weight=1)
        self.status_label = ttk.Label(status_row, text="", style="Status.TLabel")
        self.status_label.grid(row=0, column=0, sticky="w")
        self.open_button = ttk.Button(
            status_row,
            text="Open downloads folder",
            style="Secondary.TButton",
            command=self.open_download_folder,
        )
        self.open_button.grid(row=0, column=1, sticky="e")
        self.progress = ttk.Progressbar(
            download_card,
            mode="determinate",
            style="Horizontal.TProgressbar",
        )
        self.progress.grid(row=8, column=0, sticky="ew", pady=(12, 0))

        self.download_button = ttk.Button(
            content,
            text="↓   Download video",
            style="Primary.TButton",
            command=self.start_download,
            state="disabled",
        )
        self.download_button.grid(row=4, column=0, sticky="e", pady=(16, 0))

    def set_busy(self, busy):
        self.lookup_button.config(state="disabled" if busy else "normal")
        self.configure(cursor="wait" if busy else "")
        if busy or not self.selected_height:
            self.download_button.config(state="disabled")
        else:
            self.download_button.config(state="normal")

    def lookup(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Missing link", "Enter a YouTube video link.")
            return

        for child in self.quality_frame.winfo_children():
            child.destroy()
        self.current_qualities = []
        self.selected_height = None
        self.video_title.config(text="Looking up video...")
        self.video_meta.config(text="Checking available qualities.")
        self.status_label.config(text="Reading available qualities...")
        self.progress["value"] = 0
        self.download_button.config(state="disabled")
        self.set_busy(True)
        threading.Thread(target=self.lookup_worker, args=(url,), daemon=True).start()

    def lookup_worker(self, url):
        try:
            with yt_dlp.YoutubeDL(yt_dlp_options()) as ydl:
                info = ydl.extract_info(url, download=False)

            if info.get("is_live"):
                raise RuntimeError("Live streams are not supported.")

            qualities = {}
            combined_formats = [
                item for item in info.get("formats", [])
                if item.get("height")
                and item.get("vcodec") not in (None, "none")
                and item.get("acodec") not in (None, "none")
            ]

            for item in info.get("formats", []):
                height = item.get("height")
                if not height or item.get("vcodec") in (None, "none"):
                    continue
                if height not in qualities:
                    qualities[height] = {
                        "height": height,
                        "label": f"{height}p",
                        "size": None,
                        "needs_merge": item.get("acodec") in (None, "none"),
                    }

            for height, quality in qualities.items():
                candidates = [
                    item for item in combined_formats
                    if item.get("height") == height
                ]
                if candidates:
                    candidate = max(candidates, key=lambda item: item.get("tbr") or 0)
                    quality["needs_merge"] = False
                else:
                    candidate = max(
                        [
                            item for item in info.get("formats", [])
                            if item.get("height") == height
                            and item.get("vcodec") not in (None, "none")
                        ],
                        key=lambda item: item.get("tbr") or 0,
                        default=None,
                    )
                if candidate:
                    quality["size"] = format_size(
                        candidate.get("filesize") or candidate.get("filesize_approx")
                    )

            duration = info.get("duration")
            duration_text = ""
            if duration:
                hours, remainder = divmod(int(duration), 3600)
                minutes, seconds = divmod(remainder, 60)
                duration_text = (
                    f"{hours}:{minutes:02d}:{seconds:02d}"
                    if hours
                    else f"{minutes}:{seconds:02d}"
                )

            result = {
                "title": info.get("title") or "YouTube video",
                "channel": info.get("channel") or info.get("uploader") or "YouTube",
                "duration": duration_text,
                "qualities": sorted(qualities.values(), key=lambda item: item["height"], reverse=True),
            }
            self.after(0, self.show_lookup_result, result)
        except Exception as exc:
            message = str(exc).strip() or "Could not read this video."
            self.after(0, self.show_lookup_error, message)

    def show_lookup_result(self, result):
        self.set_busy(False)
        if not result["qualities"]:
            self.status_label.config(text="No downloadable video qualities were found.")
            return

        meta = result["channel"]
        if result["duration"]:
            meta += f"  ·  {result['duration']}"
        self.video_title.config(text=result["title"])
        self.video_meta.config(text=meta)
        self.status_label.config(text="")
        self.current_qualities = result["qualities"]

        for index, quality in enumerate(self.current_qualities):
            button = ttk.Button(
                self.quality_frame,
                text=f"{quality['label']}\n{quality['size'] or 'Size varies'}",
                style="Quality.TButton",
                command=lambda selected=quality: self.select_quality(selected),
            )
            button.grid(
                row=index // 4,
                column=index % 4,
                sticky="ew",
                padx=(0, 8 if index % 4 < 3 else 0),
                pady=(0, 8),
            )
        self.select_quality(self.current_qualities[0])

    def show_lookup_error(self, message):
        self.set_busy(False)
        self.status_label.config(text="")
        messagebox.showerror("Unable to read video", message)

    def select_quality(self, quality):
        self.selected_height = str(quality["height"])
        for child in self.quality_frame.winfo_children():
            selected = child.cget("text").startswith(quality["label"])
            child.configure(
                style="SelectedQuality.TButton" if selected else "Quality.TButton"
            )
        self.download_button.config(state="normal")

    def start_download(self):
        url = self.url_entry.get().strip()
        if not url or not self.selected_height:
            return
        if self.download_thread and self.download_thread.is_alive():
            return

        self.lookup_button.config(state="disabled")
        self.download_button.config(state="disabled")
        self.progress["value"] = 0
        self.status_label.config(text="Starting download...")
        self.download_thread = threading.Thread(
            target=self.download_worker,
            args=(url, self.selected_height),
            daemon=True,
        )
        self.download_thread.start()

    def download_worker(self, url, height):
        def progress_hook(status):
            if status["status"] == "downloading":
                percent_text = status.get("_percent_str", "").strip().replace("%", "")
                try:
                    percent = max(0, min(100, int(float(percent_text))))
                except (TypeError, ValueError):
                    return
                self.after(0, self.update_download_progress, percent, "Downloading...")
            elif status["status"] == "finished":
                self.after(0, self.update_download_progress, 100, "Processing and merging...")

        options = yt_dlp_options()
        options.update({
            "format": f"bv*[height={height}]+ba/b[height={height}]",
            "merge_output_format": "mp4",
            "outtmpl": str(DOWNLOAD_DIR / "%(title)s [%(height)sP].%(ext)s"),
            "progress_hooks": [progress_hook],
        })

        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.add_post_processor(H264AacMp4PostProcessor(ydl), when="post_process")
                ydl.extract_info(url, download=True)
            self.after(0, self.download_complete)
        except Exception as exc:
            message = str(exc).strip() or "Download failed."
            self.after(0, self.download_failed, message)

    def update_download_progress(self, percent, status):
        self.progress["value"] = percent
        self.status_label.config(text=f"{status}  {percent}%")

    def download_complete(self):
        self.progress["value"] = 100
        self.status_label.config(text="Download complete.")
        self.lookup_button.config(state="normal")
        self.download_button.config(state="normal")
        if messagebox.askyesno(
            "Download complete",
            "The video was downloaded successfully.\n\nOpen the downloads folder?",
        ):
            self.open_download_folder()

    def download_failed(self, message):
        self.status_label.config(text="")
        self.lookup_button.config(state="normal")
        self.download_button.config(state="normal" if self.selected_height else "disabled")
        messagebox.showerror("Download failed", message)

    def open_download_folder(self):
        os.startfile(DOWNLOAD_DIR)


if __name__ == "__main__":
    app = VideoDownloaderApp()
    app.mainloop()
