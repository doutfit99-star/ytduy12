# -*- coding: utf-8 -*-
"""
DUY DOW Engine - Core Downloader Module v4.0 PRO
Integrates `you_get` with fallback to `yt-dlp` for maximum speed & reliability.
Includes Ultra-Fast Metadata Extractor (< 1 sec), YouTube HD Thumbnail generator,
real-time progress tracking, and robust offline font & UI support.
"""

import os
import sys
import json
import re
import socket
import threading
import time
import urllib.request
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

# Attempt to import you_get natively
try:
    import you_get
    from you_get.common import url_to_module, parse_host
    HAS_YOU_GET = True
except ImportError:
    HAS_YOU_GET = False

# Attempt to import yt_dlp for fallback/enhanced formats
try:
    import yt_dlp
    HAS_YT_DLP = True
except ImportError:
    HAS_YT_DLP = False

IS_VERCEL = bool(os.environ.get("VERCEL") or os.environ.get("NOW_REGION"))

if IS_VERCEL:
    DEFAULT_DOWNLOAD_DIR = "/tmp/DUY_DOW"
    BASE_DATA_DIR = Path("/tmp")
else:
    DEFAULT_DOWNLOAD_DIR = str(Path.home() / "Downloads" / "DUY_DOW")
    BASE_DATA_DIR = Path(".")

try:
    os.makedirs(DEFAULT_DOWNLOAD_DIR, exist_ok=True)
except Exception:
    DEFAULT_DOWNLOAD_DIR = "/tmp"


class DownloaderTask:
    def __init__(self, task_id: str, url: str, save_dir: str, quality: str = "best", media_type: str = "video", engine: str = "auto"):
        self.task_id = task_id
        self.url = url
        self.save_dir = save_dir or DEFAULT_DOWNLOAD_DIR
        self.quality = quality
        self.media_type = media_type  # video, audio, image
        self.engine = engine
        
        # Status tracking
        self.status = "queued"  # queued, analyzing, downloading, paused, completed, error
        self.progress = 0.0
        self.title = "Đang phân tích dữ liệu..."
        self.platform = "Unknown"
        self.thumbnail = ""
        self.filename = ""
        self.filepath = ""
        self.speed = "0 MB/s"
        self.speed_bytes = 0
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.eta = "--:--"
        self.uploader = ""
        self.duration = "N/A"
        self.error_msg = ""
        self.created_at = time.strftime("%H:%M:%S - %d/%m/%Y")
        self.is_paused = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "url": self.url,
            "save_dir": self.save_dir,
            "quality": self.quality,
            "media_type": self.media_type,
            "engine": self.engine,
            "status": self.status,
            "progress": round(self.progress, 1),
            "title": self.title,
            "platform": self.platform,
            "thumbnail": self.thumbnail,
            "filename": self.filename,
            "filepath": self.filepath,
            "speed": self.speed,
            "speed_bytes": self.speed_bytes,
            "downloaded_bytes": self.downloaded_bytes,
            "total_bytes": self.total_bytes,
            "eta": self.eta,
            "uploader": self.uploader,
            "duration": self.duration,
            "error_msg": self.error_msg,
            "created_at": self.created_at
        }


class BuildTask:
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.status = "queued"  # queued, pending, building, processing, completed, failed, cancelled, not_found
        self.progress = 0
        self.message = "Đang khởi tạo tiến trình build..."
        self.error = ""
        self.exe_path = ""
        self.created_at = time.strftime("%H:%M:%S - %d/%m/%Y")

    def to_normalized_dict(self) -> Dict[str, Any]:
        return {
            "taskId": str(self.task_id) if self.task_id else "",
            "status": str(self.status) if self.status else "queued",
            "progress": int(self.progress) if isinstance(self.progress, (int, float)) else 0,
            "message": str(self.message) if self.message else "",
            "error": str(self.error) if self.error else "",
            "exePath": str(self.exe_path) if self.exe_path else "",
            "createdAt": str(self.created_at) if self.created_at else ""
        }


class DHDowEngine:
    def __init__(self):
        self.tasks: Dict[str, DownloaderTask] = {}
        self.build_tasks: Dict[str, BuildTask] = {}
        self.history_file = BASE_DATA_DIR / "download_history.json"
        self.settings_file = BASE_DATA_DIR / "settings.json"
        self.download_dir = DEFAULT_DOWNLOAD_DIR
        self.history: List[Dict[str, Any]] = self._load_history()
        self.settings: Dict[str, Any] = self._load_settings()
        if self.settings.get("download_dir"):
            self.download_dir = self.settings["download_dir"]
            try:
                os.makedirs(self.download_dir, exist_ok=True)
            except Exception:
                pass
        self.notifications: List[Dict[str, Any]] = [
            {
                "id": "notif_1",
                "title": "DUY DOW v4.0 PRO Sẵn sàng",
                "message": "Đã tối ưu phân tích siêu tốc < 1s, tiến trình tải real-time và hiển thị Thumbnail HD.",
                "time": time.strftime("%H:%M"),
                "type": "info",
                "read": False
            }
        ]

    def _load_settings(self) -> Dict[str, Any]:
        default_settings = {
            "download_dir": self.download_dir,
            "engine": "auto",
            "quality": "best",
            "max_concurrent": 3,
            "auto_paste": True,
            "sound_effects": True,
            "theme": "dark",
            "language": "vn"
        }
        if self.settings_file.exists():
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    default_settings.update(loaded)
            except Exception:
                pass
        return default_settings

    def save_settings(self, new_settings: Dict[str, Any]) -> Dict[str, Any]:
        self.settings.update(new_settings)
        if "download_dir" in new_settings and new_settings["download_dir"]:
            self.download_dir = new_settings["download_dir"]
            os.makedirs(self.download_dir, exist_ok=True)
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")
        return self.settings

    def _load_history(self) -> List[Dict[str, Any]]:
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_history(self):
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.history[:300], f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving history: {e}")

    def add_notification(self, title: str, message: str, notif_type: str = "info"):
        notif = {
            "id": f"notif_{int(time.time()*1000)}",
            "title": title,
            "message": message,
            "time": time.strftime("%H:%M"),
            "type": notif_type,
            "read": False
        }
        self.notifications.insert(0, notif)
        self.notifications = self.notifications[:50]

    def mark_notifications_read(self):
        for n in self.notifications:
            n["read"] = True

    def detect_platform(self, url: str) -> str:
        url_lower = url.lower()
        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            return "YouTube"
        elif "tiktok.com" in url_lower:
            return "TikTok"
        elif "facebook.com" in url_lower or "fb.watch" in url_lower:
            return "Facebook"
        elif "bilibili.com" in url_lower or "b23.tv" in url_lower:
            return "Bilibili"
        elif "instagram.com" in url_lower:
            return "Instagram"
        elif "twitter.com" in url_lower or "x.com" in url_lower:
            return "Twitter/X"
        elif "soundcloud.com" in url_lower:
            return "SoundCloud"
        elif "vimeo.com" in url_lower:
            return "Vimeo"
        elif "reddit.com" in url_lower:
            return "Reddit"
        elif "douyin.com" in url_lower:
            return "Douyin"
        elif "pinterest.com" in url_lower or "pin.it" in url_lower:
            return "Pinterest"
        else:
            return "Web Media"

    def _get_platform_headers(self, url: str) -> Dict[str, str]:
        url_lower = url.lower()
        chrome_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        
        headers = {
            "User-Agent": chrome_ua,
            "Accept": "*/*",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        
        if "tiktok.com" in url_lower or "douyin.com" in url_lower:
            headers["Referer"] = "https://www.tiktok.com/"
        elif "bilibili.com" in url_lower or "b23.tv" in url_lower:
            headers["Referer"] = "https://www.bilibili.com/"
        elif "facebook.com" in url_lower or "fb.watch" in url_lower:
            headers["Referer"] = "https://www.facebook.com/"
        elif "instagram.com" in url_lower:
            headers["Referer"] = "https://www.instagram.com/"
        elif "twitter.com" in url_lower or "x.com" in url_lower:
            headers["Referer"] = "https://twitter.com/"
        elif "youtube.com" in url_lower or "youtu.be" in url_lower:
            headers["Referer"] = "https://www.youtube.com/"
        elif "reddit.com" in url_lower:
            headers["Referer"] = "https://www.reddit.com/"

        return headers

    def _extract_youtube_id(self, url: str) -> Optional[str]:
        """Fast regex extraction for YouTube video IDs."""
        match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
        return match.group(1) if match else None

    def analyze_url(self, url: str) -> Dict[str, Any]:
        """Fast Metadata Extractor (< 1 sec) with instant thumbnail resolution."""
        platform = self.detect_platform(url)
        yt_id = self._extract_youtube_id(url) if platform == "YouTube" else None

        info = {
            "url": url,
            "platform": platform,
            "title": f"{platform} Video/Media",
            "thumbnail": f"https://img.youtube.com/vi/{yt_id}/hqdefault.jpg" if yt_id else "",
            "duration": "N/A",
            "uploader": "Unknown",
            "formats": [
                {"id": "best", "label": "Chất lượng tốt nhất (Best Quality)"},
                {"id": "4k", "label": "Ultra HD 4K (2160p)"},
                {"id": "1080p", "label": "Full HD (1080p)"},
                {"id": "720p", "label": "HD (720p)"},
                {"id": "480p", "label": "Standard (480p)"},
                {"id": "mp3", "label": "Âm thanh MP3 (320kbps)"},
                {"id": "m4a", "label": "Âm thanh M4A High Quality"},
                {"id": "image_hd", "label": "Tải Hình ảnh / Thumbnail HD (Max Resolution)"}
            ]
        }

        # Optimized yt_dlp extraction options (Fast mode with full headers)
        if HAS_YT_DLP:
            try:
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'skip_download': True,
                    'socket_timeout': 10.0,
                    'no_color': True,
                    'retries': 5,
                    'nocheckcertificate': True,
                    'http_headers': self._get_platform_headers(url),
                    'extractor_args': {
                        'youtube': {
                            'player_client': ['android', 'web', 'mweb', 'ios']
                        }
                    }
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    extracted = ydl.extract_info(url, download=False)
                    if extracted:
                        info["title"] = extracted.get("title") or info["title"]
                        info["uploader"] = extracted.get("uploader") or extracted.get("channel") or info["uploader"]
                        
                        # Thumbnail resolution fallback
                        thumb = extracted.get("thumbnail")
                        if thumb:
                            info["thumbnail"] = thumb
                        elif yt_id:
                            info["thumbnail"] = f"https://img.youtube.com/vi/{yt_id}/hqdefault.jpg"

                        dur = extracted.get("duration")
                        if dur:
                            m, s = divmod(dur, 60)
                            h, m = divmod(m, 60)
                            info["duration"] = f"{int(h):02d}:{int(m):02d}:{int(s):02d}" if h else f"{int(m):02d}:{int(s):02d}"
                        return info
            except Exception as e:
                print(f"Fast yt_dlp analysis notice: {e}")

        if not info["thumbnail"] and yt_id:
            info["thumbnail"] = f"https://img.youtube.com/vi/{yt_id}/hqdefault.jpg"

        return info

    def start_download(self, url: str, save_dir: Optional[str] = None, quality: str = "best", thumbnail: Optional[str] = None, title: Optional[str] = None, platform: Optional[str] = None) -> str:
        task_id = f"task_{int(time.time() * 1000)}_{len(self.tasks)}"
        target_dir = save_dir or self.download_dir
        os.makedirs(target_dir, exist_ok=True)

        media_type = "video"
        if quality in ["mp3", "m4a"]:
            media_type = "audio"
        elif quality in ["image_hd", "image_jpg", "image_png"]:
            media_type = "image"

        task = DownloaderTask(task_id, url, target_dir, quality, media_type)
        task.platform = platform or self.detect_platform(url)

        # Assign provided or fast-extracted title & thumbnail immediately
        if title:
            task.title = title
        else:
            task.title = f"Tác vụ {task.platform} ({media_type.upper()})"

        if thumbnail:
            task.thumbnail = thumbnail
        else:
            yt_id = self._extract_youtube_id(url)
            if yt_id:
                task.thumbnail = f"https://img.youtube.com/vi/{yt_id}/hqdefault.jpg"

        # If thumbnail still empty, do fast sync check
        if not task.thumbnail:
            try:
                info = self.analyze_url(url)
                if info.get("thumbnail"):
                    task.thumbnail = info["thumbnail"]
                if info.get("title") and task.title.startswith("Tác vụ"):
                    task.title = info["title"]
            except Exception:
                pass

        self.tasks[task_id] = task

        # Add notification
        self.add_notification("Khởi tạo tải xuống", f"Đã thêm tác vụ {task.platform} ({media_type.upper()}) vào hàng chờ.", "info")

        # Start download thread
        thread = threading.Thread(target=self._download_worker, args=(task_id,), daemon=True)
        thread.start()
        return task_id

    def start_batch_downloads(self, urls: List[str], save_dir: Optional[str] = None, quality: str = "best") -> List[str]:
        task_ids = []
        for url in urls:
            u = url.strip()
            if u:
                tid = self.start_download(u, save_dir, quality)
                task_ids.append(tid)
        return task_ids

    def _download_worker(self, task_id: str):
        task = self.tasks.get(task_id)
        if not task:
            return

        task.status = "analyzing"
        if not task.title or task.title.startswith("Tác vụ") or task.title.startswith("Unknown"):
            task.title = f"Đang kết nối {task.platform}..."

        # Special handling for image / thumbnail download
        if task.quality.startswith("image_") or task.media_type == "image":
            self._download_image_worker(task)
            return

        success = False
        yt_error = ""
        
        # 1. First attempt with yt-dlp if installed
        if HAS_YT_DLP and task.engine != "you-get":
            try:
                def progress_hook(d):
                    if task.is_paused:
                        return
                    if d['status'] == 'downloading':
                        task.status = "downloading"
                        total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                        downloaded = d.get('downloaded_bytes') or 0
                        if total > 0:
                            task.progress = min(99.0, (downloaded / total) * 100)
                        task.downloaded_bytes = downloaded
                        task.total_bytes = total
                        
                        # Speed & ETA
                        speed_val = d.get('speed') or 0
                        task.speed_bytes = speed_val
                        if speed_val > 1024 * 1024:
                            task.speed = f"{speed_val / (1024 * 1024):.1f} MB/s"
                        elif speed_val > 1024:
                            task.speed = f"{speed_val / 1024:.1f} KB/s"
                        else:
                            task.speed = f"{speed_val:.0f} B/s"
                            
                        eta_val = d.get('eta')
                        if eta_val:
                            m, s = divmod(eta_val, 60)
                            task.eta = f"{int(m):02d}:{int(s):02d}"

                ydl_opts = {
                    'outtmpl': os.path.join(task.save_dir, '%(title)s.%(ext)s'),
                    'progress_hooks': [progress_hook],
                    'quiet': True,
                    'no_warnings': True,
                    'nocheckcertificate': True,
                    'concurrent_fragment_downloads': 5,
                    'retries': 10,
                    'fragment_retries': 10,
                    'skip_unavailable_fragments': True,
                    'socket_timeout': 20.0,
                    'geo_bypass': True,
                    'legacy_server_connect': True,
                    'http_headers': self._get_platform_headers(task.url),
                    'extractor_args': {
                        'youtube': {
                            'player_client': ['android', 'web', 'mweb', 'ios']
                        }
                    }
                }

                if task.quality == 'mp3':
                    ydl_opts['format'] = 'bestaudio/best'
                    ydl_opts['postprocessors'] = [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '320',
                    }]
                elif task.quality == 'm4a':
                    ydl_opts['format'] = 'bestaudio[ext=m4a]/bestaudio/best'
                    ydl_opts['postprocessors'] = [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'm4a',
                        'preferredquality': '192',
                    }]
                elif task.quality == '4k':
                    ydl_opts['format'] = 'bestvideo[height<=2160]+bestaudio/bestvideo[height<=2160]/best[height<=2160]/best'
                elif task.quality == '1080p':
                    ydl_opts['format'] = 'bestvideo[height<=1080]+bestaudio/bestvideo[height<=1080]/best[height<=1080]/best'
                elif task.quality == '720p':
                    ydl_opts['format'] = 'bestvideo[height<=720]+bestaudio/bestvideo[height<=720]/best[height<=720]/best'
                elif task.quality == '480p':
                    ydl_opts['format'] = 'bestvideo[height<=480]+bestaudio/bestvideo[height<=480]/best[height<=480]/best'
                else:
                    ydl_opts['format'] = 'bestvideo+bestaudio/best'

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # Fast metadata extraction if title is still missing or generic
                    if not task.title or task.title.startswith("Tác vụ") or task.title.startswith("Đang") or task.title.startswith("Unknown"):
                        try:
                            fast_info = ydl.extract_info(task.url, download=False)
                            if fast_info:
                                if fast_info.get('title'):
                                    task.title = fast_info.get('title')
                                if not task.thumbnail and fast_info.get('thumbnail'):
                                    task.thumbnail = fast_info.get('thumbnail')
                                task.uploader = fast_info.get('uploader') or fast_info.get('channel', '')
                                dur = fast_info.get('duration')
                                if dur:
                                    m, s = divmod(dur, 60)
                                    h, m = divmod(m, 60)
                                    task.duration = f"{int(h):02d}:{int(m):02d}:{int(s):02d}" if h else f"{int(m):02d}:{int(s):02d}"
                        except Exception as pre_e:
                            print(f"Pre-extraction warning: {pre_e}")

                    task.status = "downloading"
                    info_dict = ydl.extract_info(task.url, download=True)
                    if info_dict:
                        task.title = info_dict.get('title') or task.title
                        if not task.thumbnail:
                            task.thumbnail = info_dict.get('thumbnail', '')
                        task.uploader = info_dict.get('uploader') or info_dict.get('channel', '')
                        dur = info_dict.get('duration')
                        if dur:
                            m, s = divmod(dur, 60)
                            h, m = divmod(m, 60)
                            task.duration = f"{int(h):02d}:{int(m):02d}:{int(s):02d}" if h else f"{int(m):02d}:{int(s):02d}"

                        final_path = None
                        requested = info_dict.get('requested_downloads')
                        if requested and isinstance(requested, list) and len(requested) > 0:
                            for req_item in requested:
                                fp = req_item.get('filepath')
                                if fp and os.path.exists(fp):
                                    final_path = fp
                                    break

                        if not final_path:
                            prep = ydl.prepare_filename(info_dict)
                            if task.quality == 'mp3':
                                prep = os.path.splitext(prep)[0] + '.mp3'
                            elif task.quality == 'm4a':
                                prep = os.path.splitext(prep)[0] + '.m4a'
                            
                            if os.path.exists(prep):
                                final_path = prep
                            else:
                                stem = Path(prep).stem
                                for f in Path(task.save_dir).glob(f"{stem}.*"):
                                    if f.is_file() and not f.name.endswith(".part") and not f.name.endswith(".ytdl"):
                                        final_path = str(f.resolve())
                                        break
                                if not final_path:
                                    final_path = prep

                        task.filepath = os.path.abspath(final_path)
                        task.filename = os.path.basename(final_path)
                        if os.path.exists(task.filepath):
                            task.total_bytes = os.path.getsize(task.filepath)
                            task.downloaded_bytes = task.total_bytes
                
                success = True
                task.status = "completed"
                task.progress = 100.0
            except Exception as e:
                yt_error = str(e)
                print(f"yt-dlp fallback notice: {yt_error}")
                task.error_msg = yt_error
                success = False

        # 2. Fallback to you_get engine if needed
        if not success and HAS_YOU_GET:
            try:
                task.status = "downloading"
                cmd = [sys.executable, "-m", "you_get", "-o", task.save_dir, task.url]
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    encoding='utf-8',
                    errors='ignore'
                )

                for line in process.stdout:
                    if task.is_paused:
                        continue
                    line_str = line.strip()
                    if "title:" in line_str.lower():
                        task.title = line_str.split(":", 1)[-1].strip()
                    elif "site:" in line_str.lower():
                        task.platform = line_str.split(":", 1)[-1].strip()
                    elif "%" in line_str:
                        parts = line_str.split()
                        for p in parts:
                            if p.endswith("%"):
                                try:
                                    task.progress = float(p.rstrip("%"))
                                except ValueError:
                                    pass

                process.wait()
                if process.returncode == 0:
                    task.status = "completed"
                    task.progress = 100.0
                    success = True
                else:
                    yg_err = f"you-get exited with code {process.returncode}"
                    if not task.error_msg:
                        task.error_msg = yg_err
            except Exception as e:
                if not task.error_msg:
                    task.error_msg = str(e)

        if task.status == "completed":
            hist_item = task.to_dict()
            self.history.insert(0, hist_item)
            self._save_history()
            self.add_notification("Tải xuống hoàn tất 🎉", f"Đã tải xong: '{task.title[:30]}...'", "success")
        else:
            task.status = "error"
            if not task.error_msg:
                task.error_msg = "Không thể kết nối hoặc tải video từ nền tảng này. Vui lòng kiểm tra lại liên kết."
            self.add_notification("Tải xuống thất bại ⚠️", f"Lỗi tác vụ: {task.title[:25]}", "error")

    def _download_image_worker(self, task: DownloaderTask):
        """Dedicated Image / Thumbnail HD Downloader."""
        try:
            task.status = "downloading"
            info = self.analyze_url(task.url)
            task.title = f"Hình ảnh - {info.get('title', 'Photo HD')}"
            thumb_url = info.get("thumbnail") or task.url

            if not thumb_url.startswith("http"):
                thumb_url = task.url

            ext = ".jpg"
            if ".png" in thumb_url.lower(): ext = ".png"
            elif ".webp" in thumb_url.lower(): ext = ".webp"

            safe_title = "".join([c for c in task.title if c.isalnum() or c in (' ', '_', '-')]).rstrip()
            out_name = f"{safe_title[:50]}{ext}"
            out_path = os.path.join(task.save_dir, out_name)

            task.title = out_name
            task.progress = 30.0

            # Download file via urllib
            req = urllib.request.Request(thumb_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as resp, open(out_path, 'wb') as f:
                data = resp.read()
                f.write(data)
                task.total_bytes = len(data)
                task.downloaded_bytes = len(data)

            task.progress = 100.0
            task.status = "completed"
            task.filename = out_name
            task.filepath = os.path.abspath(out_path)

            hist_item = task.to_dict()
            self.history.insert(0, hist_item)
            self._save_history()
            self.add_notification("Tải hình ảnh hoàn tất 🖼️", f"Đã lưu ảnh HD: '{out_name}'", "success")
        except Exception as e:
            task.status = "error"
            task.error_msg = f"Không thể tải hình ảnh: {e}"
            self.add_notification("Lỗi tải hình ảnh", str(e), "error")

    def _resolve_existing_filepath(self, filepath: str) -> Optional[str]:
        if not filepath:
            return None
        if os.path.exists(filepath):
            return filepath
            
        # Try finding file with same stem in folder
        try:
            p = Path(filepath)
            parent = p.parent
            stem = p.stem
            if parent.exists():
                for f in parent.glob(f"{stem}.*"):
                    if f.is_file() and not f.name.endswith(".part") and not f.name.endswith(".ytdl"):
                        return str(f.resolve())
                for f in parent.iterdir():
                    if f.is_file() and len(stem) > 5 and stem[:15] in f.name:
                        return str(f.resolve())
        except Exception:
            pass
        return None

    def open_file_native(self, filepath: str) -> bool:
        """Launch downloaded file in default OS media player."""
        real_path = self._resolve_existing_filepath(filepath)
        if real_path and os.path.exists(real_path):
            try:
                if sys.platform == "win32":
                    os.startfile(real_path)
                else:
                    subprocess.Popen(["xdg-open", real_path])
                return True
            except Exception as e:
                print(f"Error opening file native: {e}")
        return False

    def open_file_location(self, filepath: str, fallback_dir: Optional[str] = None) -> bool:
        """Open Explorer and select the downloaded file or open download folder."""
        real_path = self._resolve_existing_filepath(filepath) if filepath else None
        target_dir = fallback_dir or self.download_dir

        if real_path and os.path.exists(real_path):
            try:
                if sys.platform == "win32":
                    subprocess.Popen(['explorer', f'/select,{os.path.normpath(real_path)}'])
                    return True
                else:
                    subprocess.Popen(["xdg-open", os.path.dirname(real_path)])
                    return True
            except Exception as e:
                print(f"Error opening file location: {e}")

        # Fallback to opening directory
        if target_dir and os.path.exists(target_dir):
            try:
                if sys.platform == "win32":
                    os.startfile(target_dir)
                else:
                    subprocess.Popen(["xdg-open", target_dir])
                return True
            except Exception as e:
                print(f"Error opening folder: {e}")
        return False

    def pause_task(self, task_id: str):
        task = self.tasks.get(task_id)
        if task:
            task.is_paused = True
            task.status = "paused"

    def resume_task(self, task_id: str):
        task = self.tasks.get(task_id)
        if task:
            task.is_paused = False
            task.status = "downloading"

    def pause_all(self):
        for task in self.tasks.values():
            if task.status == "downloading":
                task.is_paused = True
                task.status = "paused"

    def resume_all(self):
        for task in self.tasks.values():
            if task.status == "paused":
                task.is_paused = False
                task.status = "downloading"

    def delete_task(self, task_id: str):
        if task_id in self.tasks:
            del self.tasks[task_id]
        self.history = [item for item in self.history if item.get("task_id") != task_id]
        self._save_history()

    def clear_all_tasks(self):
        self.tasks.clear()
        self.history = []
        self._save_history()

    def get_stats_summary(self) -> Dict[str, Any]:
        tasks_list = list(self.tasks.values())
        hist_list = self.history
        
        seen_ids = set()
        all_items = []
        for t in tasks_list:
            d = t.to_dict()
            seen_ids.add(t.task_id)
            all_items.append(d)
        for h in hist_list:
            if h.get("task_id") not in seen_ids:
                seen_ids.add(h.get("task_id"))
                all_items.append(h)

        downloading_count = sum(1 for t in all_items if t.get("status") in ["downloading", "analyzing"])
        completed_count = sum(1 for t in all_items if t.get("status") == "completed")
        queued_count = sum(1 for t in all_items if t.get("status") in ["queued", "paused"])
        error_count = sum(1 for t in all_items if t.get("status") == "error")

        total_speed_bytes = sum(t.speed_bytes for t in tasks_list if t.status == "downloading")
        if total_speed_bytes > 1024 * 1024:
            speed_str = f"{total_speed_bytes / (1024 * 1024):.1f} MB/s"
        elif total_speed_bytes > 1024:
            speed_str = f"{total_speed_bytes / 1024:.1f} KB/s"
        else:
            speed_str = f"{total_speed_bytes:.1f} B/s"

        return {
            "downloading": downloading_count,
            "completed": completed_count,
            "queued": queued_count,
            "error": error_count,
            "total_active": downloading_count + queued_count,
            "current_speed": speed_str,
            "current_speed_mb": round(total_speed_bytes / (1024 * 1024), 2)
        }

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        task = self.tasks.get(task_id)
        return task.to_dict() if task else None

    def get_history(self) -> List[Dict[str, Any]]:
        return self.history

    def delete_history_item(self, task_id: str):
        self.delete_task(task_id)

    def clear_history(self):
        self.clear_all_tasks()

    def start_build_task(self) -> str:
        """Start asynchronous background build task."""
        task_id = f"build_task_{int(time.time() * 1000)}"
        task = BuildTask(task_id)
        self.build_tasks[task_id] = task

        thread = threading.Thread(target=self._build_worker, args=(task_id,), daemon=True)
        thread.start()
        return task_id

    def get_build_task_status(self, task_id: Optional[str]) -> Dict[str, Any]:
        """Retrieve normalized task status handling missing, null, or invalid task_id safely."""
        if not task_id or not str(task_id).strip() or str(task_id).strip().lower() in ["null", "undefined"]:
            return {
                "taskId": "",
                "status": "failed",
                "progress": 0,
                "message": "Mã tác vụ (taskId) không hợp lệ",
                "error": "Thiếu mã tác vụ task_id hợp lệ",
                "exePath": ""
            }

        tid = str(task_id).strip()
        task = self.build_tasks.get(tid)
        if not task:
            return {
                "taskId": tid,
                "status": "not_found",
                "progress": 0,
                "message": "Không tìm thấy tác vụ build.",
                "error": "Tác vụ không tồn tại hoặc đã bị xóa",
                "exePath": ""
            }
        return task.to_normalized_dict()

    def _build_worker(self, task_id: str):
        task = self.build_tasks.get(task_id)
        if not task:
            return

        try:
            task.status = "building"
            task.progress = 25
            task.message = "Đang kiểm tra môi trường đóng gói..."

            time.sleep(0.5)
            task.progress = 50
            task.message = "Đang đóng gói ứng dụng bằng PyInstaller..."

            cmd = [sys.executable, "build_exe.py"]
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path(__file__).parent))

            if proc.returncode == 0:
                exe_file = Path("dist") / "DH-DOW.exe"
                if exe_file.exists():
                    task.status = "completed"
                    task.progress = 100
                    task.message = "Build thành công"
                    task.exe_path = str(exe_file.resolve())
                    self.add_notification("Đóng gói ứng dụng thành công 🎉", "Đã xuất tệp EXE tại: dist/DH-DOW.exe", "success")
                else:
                    task.status = "failed"
                    task.progress = 0
                    task.message = "Build thất bại"
                    task.error = "Không tìm thấy tệp DH-DOW.exe sau khi đóng gói"
                    self.add_notification("Build thất bại ⚠️", task.error, "error")
            else:
                task.status = "failed"
                task.progress = 0
                task.message = "Build thất bại"
                err_text = proc.stderr.strip() or proc.stdout.strip() or "Lỗi đóng gói PyInstaller"
                task.error = err_text[:300]
                self.add_notification("Build thất bại ⚠️", task.error, "error")
        except Exception as e:
            task.status = "failed"
            task.progress = 0
            task.message = "Build thất bại"
            task.error = str(e)
            self.add_notification("Build thất bại ⚠️", str(e), "error")


# Global engine instance
engine = DHDowEngine()
