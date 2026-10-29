import multiprocessing
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"


def _listening(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex((host, port)) == 0


def _prepare_console():
    if sys.platform != "win32":
        return
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        import ctypes

        ctypes.windll.kernel32.SetConsoleTitleW("بصمة ZKTeco")
    except Exception:
        pass


def _open_later():
    time.sleep(1.2)
    webbrowser.open(URL)


def main():
    multiprocessing.freeze_support()
    _prepare_console()
    if getattr(sys, "frozen", False):
        os.chdir(Path(sys.executable).resolve().parent)

    if _listening(HOST, PORT):
        print("النظام يعمل مسبقاً. يتم فتح المتصفح.")
        webbrowser.open(URL)
        return

    print("جاري تشغيل نظام البصمة...")
    print(f"المتصفح: {URL}")
    print("لا تغلق هذه النافذة. إغلاقها يوقف النظام.")
    threading.Thread(target=_open_later, daemon=True).start()

    import uvicorn
    from main import app

    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
