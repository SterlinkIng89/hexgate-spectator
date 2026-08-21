"""
Patches lcu_driver's process discovery to use a fast, name-only scan.

The default lcu_driver implementation calls psutil.process_iter(attrs=["cmdline"])
which on Windows reads the command-line memory of every running process, including
protected anti-cheat (Vanguard) and system processes.  This generates hundreds of
kernel syscalls and holds Python's GIL for hundreds of milliseconds each scan cycle,
causing UI stuttering and elevated CPU usage.

This module must be imported BEFORE lcu_driver to ensure the patch is applied
before any lcu_driver internals cache the original reference.
"""

import psutil
from typing import Generator


def _fast_return_ux_process() -> Generator[psutil.Process, None, None]:
    """Yields LeagueClientUx processes using name-only scanning (~3ms vs ~500ms)."""
    for process in psutil.process_iter(attrs=["name"]):
        try:
            if process.info.get("name") in ["LeagueClientUx.exe", "LeagueClientUx"]:
                yield process
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue


def apply():
    """Apply the fast process scan patch to lcu_driver."""
    import lcu_driver.utils
    import lcu_driver.connector
    lcu_driver.utils._return_ux_process = _fast_return_ux_process
    lcu_driver.connector._return_ux_process = _fast_return_ux_process
