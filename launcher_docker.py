# launcher_docker.py
"""
Odysseus Desktop Launcher (Docker edition)
==========================================
Double-click OdysseusApp.exe to:
  1. Start Docker Desktop if it is not already running.
  2. Run `docker compose up -d` in the project directory.
  3. Wait until the Odysseus web server is healthy.
  4. Open the browser automatically.
  5. Show a system-tray icon with Open / Logs / Stop / Exit options.

Building the exe:
    powershell -ExecutionPolicy Bypass -File build-desktop-app.ps1

Icon:
    Drop your icon file as `static/icon.ico` (used by PyInstaller for the exe)
    and as `static/icon.png` (used for the system-tray icon at runtime).
    If neither exists the launcher falls back to a generated branded image.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import webbrowser
import tkinter as tk
from tkinter import scrolledtext
import shutil
import socket
import logging

# ---------------------------------------------------------------------------
# Silence missing stdout/stderr in --noconsole / windowed mode
# ---------------------------------------------------------------------------
class _NullWriter:
    def write(self, _): pass
    def flush(self): pass
    def isatty(self): return False

if sys.stdout is None:
    sys.stdout = _NullWriter()
if sys.stderr is None:
    sys.stderr = _NullWriter()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    # Running as PyInstaller bundle: _MEIPASS is the temp extraction dir,
    # but the project root is the directory that contains the .exe.
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

STATIC_DIR   = os.path.join(BASE_DIR, "static")
COMPOSE_FILE = os.path.join(BASE_DIR, "docker-compose.yml")
ENV_FILE     = os.path.join(BASE_DIR, ".env")
LOG_FILE     = os.path.join(BASE_DIR, "data", "logs", "launcher.log")

# ---------------------------------------------------------------------------
# Config (read from .env when available, fallback to defaults)
# ---------------------------------------------------------------------------
def _read_env_var(key: str, default: str) -> str:
    """Read a single variable from .env without importing dotenv."""
    if os.path.exists(ENV_FILE):
        try:
            with open(ENV_FILE, encoding="utf-8-sig") as fh:
                for line in fh:
                    line = line.strip()
                    if line.startswith("#") or "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    if k.strip() == key:
                        return v.strip().strip('"').strip("'") or default
        except Exception:
            pass
    return default

APP_HOST = _read_env_var("APP_BIND", "127.0.0.1")
APP_PORT = int(_read_env_var("APP_PORT", "7000"))
APP_URL  = f"http://{APP_HOST}:{APP_PORT}"

# How long to wait for Docker Desktop to become responsive (seconds)
DOCKER_START_TIMEOUT = 120
# How long to wait for the web server to become healthy (seconds)
SERVER_START_TIMEOUT = 180
# Polling interval (seconds)
POLL_INTERVAL = 2

# ---------------------------------------------------------------------------
# Brand colours
# ---------------------------------------------------------------------------
BG        = "#1a1c23"
FG        = "#d1d4e0"
ACCENT    = "#e06c75"
MUTED     = "#5c6370"
SUCCESS   = "#98c379"
WARNING   = "#e5c07b"

# ---------------------------------------------------------------------------
# Logging (file + in-app log window)
# ---------------------------------------------------------------------------
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("odysseus.launcher")

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
_splash_root: tk.Tk | None = None
_splash_status_var: tk.StringVar | None = None
_splash_sub_var: tk.StringVar | None = None
_log_window: tk.Toplevel | None = None
_log_text: scrolledtext.ScrolledText | None = None
_compose_proc: subprocess.Popen | None = None
_stop_event = threading.Event()          # set when user clicks Stop / Exit


# ===========================================================================
# Splash screen
# ===========================================================================

def _build_splash() -> None:
    """Build and mainloop the splash screen (runs on the main thread)."""
    global _splash_root, _splash_status_var, _splash_sub_var

    root = tk.Tk()
    _splash_root = root
    root.title("Odysseus")
    root.overrideredirect(True)
    root.configure(bg=BG)
    root.config(
        highlightbackground=ACCENT,
        highlightcolor=ACCENT,
        highlightthickness=2,
    )

    W, H = 400, 200
    ws = root.winfo_screenwidth()
    hs = root.winfo_screenheight()
    root.geometry(f"{W}x{H}+{(ws - W) // 2}+{(hs - H) // 2}")
    root.attributes("-topmost", True)

    # Title row
    tk.Label(root, text="⛵ Odysseus", font=("Segoe UI", 24, "bold"),
             bg=BG, fg=ACCENT).pack(pady=(28, 0))

    # Status label (updated live)
    _splash_status_var = tk.StringVar(value="Starting up…")
    tk.Label(root, textvariable=_splash_status_var, font=("Segoe UI", 10),
             bg=BG, fg=FG).pack(pady=(10, 0))

    # Sub-status (smaller)
    _splash_sub_var = tk.StringVar(value="")
    tk.Label(root, textvariable=_splash_sub_var, font=("Segoe UI", 8, "italic"),
             bg=BG, fg=MUTED).pack(pady=(4, 0))

    root.mainloop()


def _splash_update(status: str, sub: str = "") -> None:
    """Thread-safe splash label update."""
    if _splash_root and _splash_status_var:
        try:
            _splash_root.after(0, lambda: _splash_status_var.set(status))
        except Exception:
            pass
    if _splash_root and _splash_sub_var is not None:
        try:
            _splash_root.after(0, lambda: _splash_sub_var.set(sub))
        except Exception:
            pass


def _close_splash() -> None:
    """Destroy the splash window from any thread."""
    if _splash_root:
        try:
            _splash_root.after(0, _splash_root.destroy)
        except Exception:
            pass


# ===========================================================================
# Log window (shown via tray → Logs)
# ===========================================================================

def _open_log_window() -> None:
    global _log_window, _log_text

    if _log_window and tk.Toplevel.winfo_exists(_log_window):
        _log_window.lift()
        return

    win = tk.Toplevel()
    _log_window = win
    win.title("Odysseus — Launcher Logs")
    win.configure(bg=BG)
    win.geometry("700x420")

    txt = scrolledtext.ScrolledText(
        win, bg="#0d0f13", fg=FG, font=("Consolas", 9),
        state="disabled", relief="flat", borderwidth=0,
    )
    txt.pack(fill="both", expand=True, padx=8, pady=8)
    _log_text = txt

    # Tail the log file
    def _tail():
        pos = 0
        while True:
            try:
                with open(LOG_FILE, encoding="utf-8", errors="replace") as fh:
                    fh.seek(pos)
                    chunk = fh.read(16384)
                    if chunk:
                        pos = fh.tell()
                        txt.configure(state="normal")
                        txt.insert("end", chunk)
                        txt.see("end")
                        txt.configure(state="disabled")
            except Exception:
                pass
            time.sleep(0.8)

    threading.Thread(target=_tail, daemon=True).start()
    win.mainloop()


# ===========================================================================
# Docker helpers
# ===========================================================================

def _docker_cmd(*args: str) -> list[str]:
    """Build a docker / docker compose command, resolving the binary."""
    docker_bin = shutil.which("docker") or "docker"
    return [docker_bin, *args]


def _is_docker_running() -> bool:
    """Return True if the Docker daemon is responsive."""
    try:
        result = subprocess.run(
            _docker_cmd("info"),
            capture_output=True, timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def _start_docker_desktop() -> bool:
    """
    Launch Docker Desktop on Windows and wait until the daemon is up.
    Returns True on success, False on timeout.
    """
    desktop_paths = [
        os.path.expandvars(r"%ProgramFiles%\Docker\Docker\Docker Desktop.exe"),
        os.path.expandvars(r"%LocalAppData%\Programs\Docker\Docker\Docker Desktop.exe"),
    ]
    exe = next((p for p in desktop_paths if os.path.exists(p)), None)

    if exe:
        logger.info("Launching Docker Desktop: %s", exe)
        subprocess.Popen([exe], close_fds=True)
    else:
        logger.warning("Docker Desktop executable not found; assuming Docker is available via PATH.")

    deadline = time.monotonic() + DOCKER_START_TIMEOUT
    dots = 0
    while time.monotonic() < deadline:
        if _stop_event.is_set():
            return False
        if _is_docker_running():
            logger.info("Docker daemon is ready.")
            return True
        dots += 1
        _splash_update(
            "Waiting for Docker Desktop…",
            "." * (dots % 4 + 1),
        )
        time.sleep(POLL_INTERVAL)

    logger.error("Timed out waiting for Docker Desktop (%ds).", DOCKER_START_TIMEOUT)
    return False


def _compose_up() -> subprocess.Popen | None:
    """
    Run `docker compose up -d --build` and stream its output to the log.
    Returns the Popen handle on success, None on failure.
    """
    cmd = _docker_cmd(
        "compose",
        "--file", COMPOSE_FILE,
        "up", "--detach", "--build", "--remove-orphans",
    )
    logger.info("Running: %s", " ".join(cmd))
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        logger.error("`docker` not found on PATH. Install Docker Desktop first.")
        return None

    # Stream compose output into launcher log
    def _stream():
        for line in proc.stdout:
            logger.info("[compose] %s", line.rstrip())

    threading.Thread(target=_stream, daemon=True).start()
    exit_code = proc.wait()
    if exit_code != 0:
        logger.error("docker compose up exited with code %d", exit_code)
        return None

    logger.info("docker compose up completed successfully.")
    return proc


def _compose_down() -> None:
    """Run `docker compose down` to stop the stack."""
    cmd = _docker_cmd("compose", "--file", COMPOSE_FILE, "down", "--timeout", "20")
    logger.info("Stopping stack: %s", " ".join(cmd))
    try:
        subprocess.run(cmd, cwd=BASE_DIR, timeout=60)
    except Exception as exc:
        logger.warning("compose down error: %s", exc)


# ===========================================================================
# Health check
# ===========================================================================

def _is_server_healthy(host: str = APP_HOST, port: int = APP_PORT) -> bool:
    """True when the web server's TCP port is accepting connections."""
    try:
        with socket.create_connection((host, port), timeout=3):
            return True
    except OSError:
        return False


def _wait_for_server() -> bool:
    """Poll until Odysseus is up or timeout."""
    deadline = time.monotonic() + SERVER_START_TIMEOUT
    dots = 0
    while time.monotonic() < deadline:
        if _stop_event.is_set():
            return False
        if _is_server_healthy():
            return True
        dots += 1
        _splash_update(
            "Waiting for Odysseus to start…",
            "." * (dots % 4 + 1),
        )
        time.sleep(POLL_INTERVAL)
    return False


# ===========================================================================
# System tray
# ===========================================================================

def _load_tray_icon():
    """
    Load tray icon from static/icon.png, falling back to static/icon.ico,
    then to a generated branded image.
    """
    from PIL import Image

    for candidate in (
        os.path.join(STATIC_DIR, "icon.png"),
        os.path.join(STATIC_DIR, "icon.ico"),
    ):
        if os.path.exists(candidate):
            try:
                img = Image.open(candidate).convert("RGBA").resize((64, 64))
                logger.info("Tray icon loaded from %s", candidate)
                return img
            except Exception as exc:
                logger.debug("Could not load %s: %s", candidate, exc)

    # Fallback: generate a minimal branded icon
    from PIL import ImageDraw
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    red  = (224, 108, 117, 255)
    pink = (224, 108, 117, 160)
    # Sail
    d.polygon([(32, 8), (32, 46), (10, 46)], fill=red)
    d.polygon([(32, 16), (32, 46), (50, 46)], fill=pink)
    # Hull
    d.polygon([(6, 48), (58, 48), (46, 58), (18, 58)], fill=red)
    return img


def _run_tray() -> None:
    """Set up and run the pystray icon (blocks until icon.stop())."""
    import pystray

    icon_img = _load_tray_icon()

    def _open(_icon, _item):
        webbrowser.open(APP_URL)

    def _logs(_icon, _item):
        threading.Thread(target=_open_log_window, daemon=True).start()

    def _stop(_icon, _item):
        logger.info("User requested Stop — running docker compose down.")
        _stop_event.set()
        threading.Thread(target=_compose_down, daemon=True).start()
        _icon.notify("Odysseus", "Stopping services…")

    def _exit(_icon, _item):
        logger.info("User requested Exit.")
        _stop_event.set()
        _icon.stop()
        # Give compose down a moment then hard-exit
        threading.Thread(target=_do_exit, daemon=True).start()

    def _do_exit():
        _compose_down()
        os._exit(0)

    menu = pystray.Menu(
        pystray.MenuItem("Open Odysseus",   _open,  default=True),
        pystray.MenuItem("View Logs",       _logs),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Stop Services",   _stop),
        pystray.MenuItem("Exit",            _exit),
    )

    tray = pystray.Icon(
        name="Odysseus",
        icon=icon_img,
        title="Odysseus",
        menu=menu,
    )
    tray.run()


# ===========================================================================
# Main startup sequence (runs on a background thread)
# ===========================================================================

def _startup_sequence() -> None:
    """
    Full startup: Docker → compose up → health-check → browser → tray.
    All UI updates go through _splash_update().
    """
    try:
        # 1. Ensure Docker is running
        _splash_update("Checking Docker…", "")
        logger.info("Checking Docker daemon…")

        if not _is_docker_running():
            _splash_update("Starting Docker Desktop…", "This may take up to 2 minutes")
            logger.info("Docker not running — launching Docker Desktop.")
            ok = _start_docker_desktop()
            if not ok:
                _show_error(
                    "Docker Desktop did not start in time.\n\n"
                    "Please start Docker Desktop manually and try again."
                )
                _close_splash()
                return
        else:
            logger.info("Docker daemon already running.")

        if _stop_event.is_set():
            _close_splash()
            return

        # 2. docker compose up
        _splash_update("Starting Odysseus stack…", "docker compose up -d")
        logger.info("Bringing up Docker Compose stack…")
        result = _compose_up()
        if result is None:
            _show_error(
                "Failed to start the Odysseus Docker stack.\n\n"
                "Check the logs for details (Tray → View Logs)."
            )
            _close_splash()
            return

        if _stop_event.is_set():
            _close_splash()
            return

        # 3. Wait for server to be healthy
        _splash_update("Waiting for Odysseus…", f"Connecting to {APP_URL}")
        logger.info("Waiting for server at %s…", APP_URL)
        healthy = _wait_for_server()
        if not healthy:
            _show_error(
                f"Odysseus did not become reachable at {APP_URL} in time.\n\n"
                "Check the logs and ensure no other process is using the port."
            )
            _close_splash()
            return

        logger.info("Server is healthy. Opening browser.")

        # 4. Close splash and open browser
        _close_splash()
        time.sleep(0.3)
        webbrowser.open(APP_URL)

        # 5. Run system tray (blocks until user exits)
        _run_tray()

    except Exception as exc:
        logger.exception("Startup sequence failed: %s", exc)
        _show_error(f"Unexpected error during startup:\n\n{exc}")
        _close_splash()


def _show_error(message: str) -> None:
    """Display a simple error dialog."""
    try:
        import tkinter.messagebox as mb
        _root = tk.Tk()
        _root.withdraw()
        mb.showerror("Odysseus — Startup Error", message, parent=_root)
        _root.destroy()
    except Exception:
        logger.error("Error dialog: %s", message)


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Odysseus Desktop Launcher starting (pid=%d)", os.getpid())
    logger.info("BASE_DIR: %s", BASE_DIR)
    logger.info("APP_URL:  %s", APP_URL)
    logger.info("=" * 60)

    # Start the startup sequence on a background thread so the splash
    # mainloop can run on the main thread (required on Windows).
    startup_thread = threading.Thread(target=_startup_sequence, daemon=True)
    startup_thread.start()

    # Build and mainloop the splash screen on the main thread.
    # When _startup_sequence() calls _close_splash(), mainloop() returns
    # and the process either stays alive (tray running) or exits.
    _build_splash()

    # Fallback: if splash closed but tray thread hasn't started yet, wait.
    startup_thread.join(timeout=5)
