# path_utils.py – Path resolution for PyInstaller onefile compatibility
#
# When running as a PyInstaller --onefile bundle:
#   - Bundled files (config.json, app_icon.ico) are extracted to sys._MEIPASS
#   - User data files (trading_data.json, logs/) live next to the .exe
#
# When running in development:
#   - All files are in the same directory as main.py
#
# This module provides two helpers:
#   - get_bundled_path(filename) → for READ-ONLY bundled assets
#   - get_user_data_path(filename) → for READ-WRITE user files

import sys
import os


def _get_base_dir() -> str:
    """Get the directory where bundled assets are extracted.
    In PyInstaller onefile mode: sys._MEIPASS (temp extraction dir).
    In development: directory containing main.py.
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running as PyInstaller bundle
        return sys._MEIPASS
    else:
        # Running in development
        return os.path.dirname(os.path.abspath(__file__))


def _get_exe_dir() -> str:
    """Get the directory where the .exe lives (or script dir in dev).
    This is where user-writable files should be stored.
    """
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle – exe directory
        return os.path.dirname(sys.executable)
    else:
        # Running in development
        return os.path.dirname(os.path.abspath(__file__))


def get_bundled_path(filename: str) -> str:
    """Get path to a READ-ONLY bundled asset (e.g., config.json default, icon).

    These files are bundled inside the EXE and extracted to _MEIPASS at runtime.
    Do NOT write to these paths.

    Args:
        filename: Name of the bundled file (e.g., 'config.json', 'app_icon.ico')

    Returns:
        Absolute path to the file.
    """
    return os.path.join(_get_base_dir(), filename)


def get_user_data_path(filename: str) -> str:
    """Get path to a READ-WRITE user data file (e.g., trading_data.json, logs/).

    These files live next to the .exe (or script in dev).
    They persist across application restarts.

    Args:
        filename: Name of the user file (e.g., 'trading_data.json', 'config.json')

    Returns:
        Absolute path to the file.
    """
    return os.path.join(_get_exe_dir(), filename)


def get_config_path() -> str:
    """Get the config.json path with fallback logic:

    1. Check for user-customized config next to .exe (writable location)
    2. Fall back to bundled default config inside _MEIPASS

    This allows users to override config by placing config.json next to the .exe,
    while still having a working default bundled inside.
    """
    user_config = get_user_data_path("config.json")
    if os.path.exists(user_config):
        return user_config

    # Fall back to bundled default
    return get_bundled_path("config.json")
