# -*- coding: utf-8 -*-
"""
DUY DOW Server - FastAPI Web Application & Backend APIs v3.0 PRO
Supports batch video downloads, native file launching, settings, notifications, window controls.
"""

import os
import sys
import json
import socket
import subprocess
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

# Ensure PyInstaller temp directory is in sys.path
if hasattr(sys, '_MEIPASS'):
    meipass_path = str(Path(sys._MEIPASS).resolve())
    if meipass_path not in sys.path:
        sys.path.insert(0, meipass_path)

def get_resource_path(relative_path: str) -> Path:
    """Resolve resource path for both development and PyInstaller executable."""
    if hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).parent / relative_path

from engine import engine, DEFAULT_DOWNLOAD_DIR

app = FastAPI(title="DUY DOW Server PRO", version="3.0.0")

# Reference to PyWebView window object if available
pywebview_window = None

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Resolve static directory
STATIC_DIR = get_resource_path("static")
try:
    STATIC_DIR.mkdir(exist_ok=True)
    (STATIC_DIR / "css").mkdir(exist_ok=True)
    (STATIC_DIR / "js").mkdir(exist_ok=True)
except Exception:
    pass

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class AnalyzeRequest(BaseModel):
    url: str


class DownloadRequest(BaseModel):
    url: str
    save_dir: Optional[str] = None
    quality: Optional[str] = "best"
    thumbnail: Optional[str] = None
    title: Optional[str] = None
    platform: Optional[str] = None


class BatchDownloadRequest(BaseModel):
    urls: List[str]
    save_dir: Optional[str] = None
    quality: Optional[str] = "best"


class OpenFileRequest(BaseModel):
    filepath: str


class SettingsRequest(BaseModel):
    download_dir: Optional[str] = None
    engine: Optional[str] = "auto"
    quality: Optional[str] = "best"
    max_concurrent: Optional[int] = 3
    auto_paste: Optional[bool] = True
    sound_effects: Optional[bool] = True
    theme: Optional[str] = "dark"
    language: Optional[str] = "vn"


@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>DUY DOW PRO - Video & Audio Downloader</h1><p>Static files missing</p>"


@app.get("/manifest.json")
async def get_manifest():
    manifest_path = STATIC_DIR / "manifest.json"
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            return JSONResponse(content=json.loads(f.read()))
    raise HTTPException(status_code=404, detail="Manifest not found")


@app.get("/sw.js")
async def get_service_worker():
    sw_path = STATIC_DIR / "sw.js"
    if sw_path.exists():
        with open(sw_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), media_type="application/javascript")
    raise HTTPException(status_code=404, detail="Service worker not found")


@app.get("/api/mobile-info")
async def get_mobile_info(request: Request):
    lan_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(('8.8.8.8', 80))
        lan_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    port = request.url.port or 5820
    mobile_url = f"http://{lan_ip}:{port}"
    return JSONResponse(content={
        "status": "success",
        "lan_ip": lan_ip,
        "port": port,
        "mobile_url": mobile_url,
        "app_name": "DUY DOW",
        "version": "3.5.0"
    })


@app.get("/api/download-apk")
async def download_apk():
    apk_path = get_resource_path("dist/DUY-DOW.apk")
    if not apk_path.exists():
        # Fallback to local root dist
        apk_path = Path(__file__).parent / "dist" / "DUY-DOW.apk"
    if apk_path.exists():
        return FileResponse(
            path=str(apk_path),
            filename="DUY-DOW.apk",
            media_type="application/vnd.android.package-archive"
        )
    raise HTTPException(status_code=404, detail="File APK chưa được tạo. Hãy chạy python build_mobile.py trước.")


@app.get("/api/download-mobile-bundle")
async def download_mobile_bundle():
    pkg_path = get_resource_path("dist/DUY-DOW-Mobile-Package.zip")
    if not pkg_path.exists():
        pkg_path = Path(__file__).parent / "dist" / "DUY-DOW-Mobile-Package.zip"
    if pkg_path.exists():
        return FileResponse(
            path=str(pkg_path),
            filename="DUY-DOW-Mobile-Package.zip",
            media_type="application/zip"
        )
    raise HTTPException(status_code=404, detail="Gói Mobile Package chưa được tạo.")



@app.post("/api/analyze")
async def analyze_video(req: AnalyzeRequest):
    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="URL không hợp lệ (Invalid URL)")
    info = engine.analyze_url(req.url.strip())
    return JSONResponse(content=info)


@app.post("/api/download")
async def start_download(req: DownloadRequest):
    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="URL không hợp lệ (Invalid URL)")
    task_id = engine.start_download(
        url=req.url.strip(),
        save_dir=req.save_dir or engine.download_dir,
        quality=req.quality or "best",
        thumbnail=req.thumbnail,
        title=req.title,
        platform=req.platform
    )
    task_dict = engine.get_task(task_id)
    return JSONResponse(content={"status": "success", "task_id": task_id, "task": task_dict})


@app.post("/api/batch-download")
async def start_batch_download(req: BatchDownloadRequest):
    if not req.urls or len(req.urls) == 0:
        raise HTTPException(status_code=400, detail="Danh sách URL trống (Empty URL list)")
    task_ids = engine.start_batch_downloads(
        urls=req.urls,
        save_dir=req.save_dir or engine.download_dir,
        quality=req.quality or "best"
    )
    tasks = [engine.get_task(tid) for tid in task_ids if engine.get_task(tid)]
    return JSONResponse(content={"status": "success", "task_ids": task_ids, "tasks": tasks, "count": len(task_ids)})


@app.get("/api/tasks")
async def get_all_active_tasks():
    tasks = [t.to_dict() for t in engine.tasks.values()]
    return JSONResponse(content={"tasks": tasks})


@app.get("/api/progress/{task_id}")
async def get_progress(task_id: str):
    task = engine.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return JSONResponse(content=task)


@app.get("/api/stats")
async def get_stats():
    return JSONResponse(content=engine.get_stats_summary())


@app.post("/api/tasks/pause/{task_id}")
async def pause_task(task_id: str):
    engine.pause_task(task_id)
    return JSONResponse(content={"status": "success"})


@app.post("/api/tasks/resume/{task_id}")
async def resume_task(task_id: str):
    engine.resume_task(task_id)
    return JSONResponse(content={"status": "success"})


@app.post("/api/tasks/pause-all")
async def pause_all_tasks():
    engine.pause_all()
    return JSONResponse(content={"status": "success"})


@app.post("/api/tasks/resume-all")
async def resume_all_tasks():
    engine.resume_all()
    return JSONResponse(content={"status": "success"})


@app.post("/api/tasks/clear-all")
async def clear_all_tasks():
    engine.clear_all_tasks()
    return JSONResponse(content={"status": "success"})


@app.delete("/api/tasks/{task_id}")
async def delete_single_task(task_id: str):
    engine.delete_task(task_id)
    return JSONResponse(content={"status": "success"})


@app.get("/api/notifications")
async def get_notifications():
    unread_count = sum(1 for n in engine.notifications if not n.get("read"))
    return JSONResponse(content={"notifications": engine.notifications, "unread_count": unread_count})


@app.post("/api/notifications/read")
async def mark_notifications_read():
    engine.mark_notifications_read()
    return JSONResponse(content={"status": "success"})


@app.get("/api/settings")
async def get_settings():
    return JSONResponse(content=engine.settings)


@app.post("/api/settings")
async def update_settings(req: SettingsRequest):
    updated = engine.save_settings(req.model_dump(exclude_unset=True))
    return JSONResponse(content={"status": "success", "settings": updated})


@app.get("/api/history")
async def get_history():
    return JSONResponse(content={"history": engine.get_history()})


@app.delete("/api/history/{task_id}")
async def delete_history_item(task_id: str):
    engine.delete_history_item(task_id)
    return JSONResponse(content={"status": "success"})


@app.post("/api/history/clear")
async def clear_history():
    engine.clear_history()
    return JSONResponse(content={"status": "success"})


@app.post("/api/open-file")
async def open_file(req: OpenFileRequest):
    success = engine.open_file_native(req.filepath)
    if success:
        return JSONResponse(content={"status": "success"})
    return JSONResponse(content={"status": "error", "message": "File not found or cannot be launched"})


@app.post("/api/open-file-location")
async def open_file_location(req: OpenFileRequest):
    success = engine.open_file_location(req.filepath)
    if success:
        return JSONResponse(content={"status": "success"})
    return JSONResponse(content={"status": "error", "message": "Could not open file location"})


@app.post("/api/select-folder")
async def select_folder():
    """Trigger Windows folder selection dialog using pywebview, powershell, or tkinter."""
    global pywebview_window
    selected = None
    import base64

    # 1. Try pywebview native window dialog if active
    if pywebview_window:
        try:
            import webview
            res = pywebview_window.create_file_dialog(
                webview.FOLDER_DIALOG,
                directory=engine.download_dir
            )
            if res and len(res) > 0:
                selected = str(Path(res[0]).resolve())
        except Exception as e:
            print(f"PyWebView file dialog notice: {e}")

    # 2. Try PowerShell FolderBrowserDialog with TopMost Form on Windows
    if not selected and sys.platform == "win32":
        try:
            clean_dir = os.path.normpath(engine.download_dir)
            ps_code = f"""
            [System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms') | Out-Null
            $f = New-Object System.Windows.Forms.FolderBrowserDialog
            $f.Description = 'Chọn thư mục lưu trữ DUY DOW'
            $f.ShowNewFolderButton = $true
            $clean = '{clean_dir}'
            if (Test-Path $clean) {{ $f.SelectedPath = $clean }}
            $topmost = New-Object System.Windows.Forms.Form
            $topmost.TopMost = $true
            $topmost.Height = 0
            $topmost.Width = 0
            $topmost.WindowState = [System.Windows.Forms.FormWindowState]::Minimized
            $res = $f.ShowDialog($topmost)
            $topmost.Dispose()
            if ($res -eq [System.Windows.Forms.DialogResult]::OK) {{ Write-Output $f.SelectedPath }}
            """
            encoded = base64.b64encode(ps_code.encode('utf-16le')).decode('utf-8')
            proc = subprocess.run(
                ["powershell", "-STA", "-NoProfile", "-EncodedCommand", encoded],
                capture_output=True,
                text=True,
                timeout=45
            )
            out = proc.stdout.strip()
            if proc.returncode == 0 and out and os.path.exists(out):
                selected = str(Path(out).resolve())
        except Exception as e:
            print(f"PowerShell dialog notice: {e}")

    # 3. Try Tkinter dialog as fallback
    if not selected:
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            folder = filedialog.askdirectory(initialdir=engine.download_dir, title="Chọn thư mục lưu DUY DOW")
            root.destroy()
            if folder:
                selected = str(Path(folder).resolve())
        except Exception as e:
            print(f"Tkinter dialog notice: {e}")

    if selected:
        engine.download_dir = selected
        engine.save_settings({"download_dir": selected})

    return JSONResponse(content={
        "status": "success" if selected else "cancelled",
        "save_dir": engine.download_dir
    })


@app.post("/api/open-folder")
async def open_folder():
    target = engine.download_dir
    try:
        os.makedirs(target, exist_ok=True)
    except Exception:
        pass
    if os.path.exists(target):
        if sys.platform == "win32":
            os.startfile(target)
        else:
            subprocess.Popen(["xdg-open", target])
        return JSONResponse(content={"status": "success"})
    return JSONResponse(content={"status": "error", "message": "Folder does not exist"})


@app.post("/api/window/{action}")
async def handle_window_action(action: str):
    global pywebview_window
    if pywebview_window:
        try:
            if action == "minimize":
                pywebview_window.minimize()
            elif action == "maximize":
                pywebview_window.toggle_fullscreen()
            elif action == "close":
                pywebview_window.destroy()
            return JSONResponse(content={"status": "success"})
        except Exception as e:
            print(f"Window control error: {e}")
    return JSONResponse(content={"status": "fallback", "action": action})


@app.post("/api/build")
async def trigger_build_exe():
    """Trigger background standalone EXE packaging task."""
    try:
        task_id = engine.start_build_task()
        initial_status = engine.get_build_task_status(task_id)
        return JSONResponse(content={"status": "success", "taskId": task_id, "task": initial_status})
    except Exception as e:
        return JSONResponse(content={
            "taskId": "",
            "status": "failed",
            "progress": 0,
            "message": "Build thất bại",
            "error": str(e),
            "exePath": ""
        }, status_code=500)


@app.get("/api/build-status/{task_id}")
async def get_build_status(task_id: str):
    """Retrieve normalized status for build task."""
    status_data = engine.get_build_task_status(task_id)
    return JSONResponse(content=status_data)


@app.get("/api/info")
async def get_info():
    return JSONResponse(content={
        "app_name": "DUY DOW PRO",
        "version": "3.0.0",
        "download_dir": engine.download_dir,
        "contact": {
            "phone": "0862.610.313",
            "facebook": "https://www.facebook.com/ducduy2512",
            "zalo": "0862.610.313"
        }
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=5820, reload=True)
