import os
import sys
from pathlib import Path


def frozen():
    return bool(getattr(sys, "frozen", False))


def bundle_root():
    if frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent.parent


def frontend_dist():
    return bundle_root() / "frontend" / "dist"


def database_file():
    if frozen():
        folder = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ZKT-Basma"
    else:
        folder = Path(__file__).resolve().parent / "data"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "attendance.db"
