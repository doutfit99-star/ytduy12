# -*- coding: utf-8 -*-
"""
DUY DOW PRO - Standalone Desktop Application Launcher
Uses explicit asyncio event loop for Uvicorn server in background thread,
guaranteeing 100% reliable local server binding without ERR_CONNECTION_REFUSED.
Includes NullStream wrapper for PyInstaller --noconsole windowed executable compatibility.
"""

import sys
import os
import io
import time
import socket
import threading
import urllib.request
import webbrowser
from pathlib import Path

# Safe NullStream to prevent 'NoneType' object has no attribute 'buffer' in PyInstaller --noconsole mode
class NullStream(io.TextIOBase):
    def __init__(self):
        super().__init__()
        self.buffer = io.BytesIO()
    def write(self, s):
        return len(s) if s else 0
    def writelines(self, lines):
        pass
    def flush(self):
        pass
    def isatty(self):
        return False

# Initialize safe stdio streams for GUI/noconsole executables
if sys.stdout is None or not hasattr(sys.stdout, 'buffer') or sys.stdout.buffer is None:
    sys.stdout = NullStream()

if sys.stderr is None or not hasattr(sys.stderr, 'buffer') or sys.stderr.buffer is None:
    sys.stderr = NullStream()

if sys.stdin is None:
    sys.stdin = io.StringIO()


# Log file for debugging standalone EXE
LOG_FILE = Path.home() / "duy_dow_app.log"

def log(msg):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass

# Add PyInstaller temp dir to sys.path
if hasattr(sys, '_MEIPASS'):
    meipass_path = str(Path(sys._MEIPASS).resolve())
    if meipass_path not in sys.path:
        sys.path.insert(0, meipass_path)
    log(f"PyInstaller MEIPASS loaded: {meipass_path}")

HOST = "127.0.0.1"
BIND_HOST = "0.0.0.0"
DEFAULT_PORT = 5820

def find_free_port(start_port=DEFAULT_PORT):
    """Find an available TCP port starting from start_port."""
    for port in range(start_port, start_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((HOST, port)) != 0:
                return port
    return start_port

PORT = find_free_port()
SERVER_URL = f"http://{HOST}:{PORT}"

def start_backend():
    """Start Uvicorn FastAPI backend server on a dedicated asyncio loop."""
    try:
        import asyncio
        import uvicorn
        from server import app

        log(f"Starting uvicorn server on {BIND_HOST}:{PORT}")
        config = uvicorn.Config(
            app,
            host=BIND_HOST,
            port=PORT,
            log_level="error",
            access_log=False,
            loop="asyncio"
        )
        server = uvicorn.Server(config)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(server.serve())
    except Exception as e:
        log(f"Backend server error: {e}")

def wait_for_server(timeout=10.0):
    """Poll server URL until it responds with HTTP 200 OK."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            req = urllib.request.Request(SERVER_URL, headers={"User-Agent": "DUY-DOW-Launcher"})
            with urllib.request.urlopen(req, timeout=0.5) as response:
                if response.status == 200:
                    log(f"Server verified ready on {SERVER_URL}")
                    return True
        except Exception:
            time.sleep(0.1)
    log(f"Server readiness timeout on {SERVER_URL}")
    return False

def main():
    log("=== DUY DOW PRO Starting ===")
    
    # 1. Start backend server in a background daemon thread
    server_thread = threading.Thread(target=start_backend, daemon=True)
    server_thread.start()

    # 2. Wait until backend server is 100% active & responding
    is_ready = wait_for_server(timeout=10.0)

    if not is_ready:
        log("Backend failed to start in time.")

    # 3. Launch UI (Attempt PyWebView native window or fallback to default browser)
    launched_native = False

    if is_ready:
        try:
            import webview
            import server
            log("Creating PyWebView window...")
            window = webview.create_window(
                title="DUY DOW - Video & Audio Downloader",
                url=SERVER_URL,
                width=1380,
                height=880,
                resizable=True,
                min_size=(1024, 700),
                background_color="#0b0d19",
                frameless=False
            )
            server.pywebview_window = window
            launched_native = True
            log("Starting PyWebView main loop...")
            webview.start()
        except Exception as e:
            log(f"PyWebView exception: {e}")
            launched_native = False

    if not launched_native and is_ready:
        log("Fallback to default browser...")
        webbrowser.open(SERVER_URL)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    main()
