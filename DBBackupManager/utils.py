import sys
from pathlib import Path

def get_project_root() -> Path:
    """
    Returns the project root directory.
    When running as a normal python script, returns the directory containing this file.
    When bundled with PyInstaller, returns the temporary MEIPASS directory where data files are extracted.
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return Path(__file__).parent
