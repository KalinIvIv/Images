"""Register / unregister the native messaging host with Chrome (per user, no admin rights)."""

import json
import os
import stat
import sys
from pathlib import Path

from . import config

HOST_NAME = 'com.photocut.host'
# Fixed by the "key" in extension/manifest.json.
EXTENSION_ID = 'dhmhjgdnpjnnfpajmflglfajjmofnjmg'
REG_KEY = rf'Software\Google\Chrome\NativeMessagingHosts\{HOST_NAME}'


def linux_manifest_dirs():
    home = Path.home()
    return [home / '.config' / 'google-chrome' / 'NativeMessagingHosts',
            home / '.config' / 'chromium' / 'NativeMessagingHosts']


def launcher_path():
    """The program Chrome should start: the EXE when frozen, otherwise a small launcher script."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable)

    app_dir = Path(__file__).resolve().parent.parent
    folder = config.config_dir()
    folder.mkdir(parents=True, exist_ok=True)
    if sys.platform == 'win32':
        path = folder / 'photocut_host.bat'
        path.write_text(f'@echo off\r\nset PYTHONPATH={app_dir}\r\n"{sys.executable}" -m photocut %*\r\n')
    else:
        path = folder / 'photocut_host.sh'
        path.write_text(f'#!/bin/sh\nPYTHONPATH="{app_dir}" exec "{sys.executable}" -m photocut "$@"\n')
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def manifest(extension_id=EXTENSION_ID):
    return {
        'name': HOST_NAME,
        'description': 'PhotoCut image saver',
        'path': str(launcher_path()),
        'type': 'stdio',
        'allowed_origins': [f'chrome-extension://{extension_id}/'],
    }


def install(target_dirs=None, extension_id=EXTENSION_ID):
    data = json.dumps(manifest(extension_id), indent=2)
    written = []
    if sys.platform == 'win32' and not target_dirs:
        import winreg
        path = config.config_dir() / f'{HOST_NAME}.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding='utf-8')
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY) as key:
            winreg.SetValueEx(key, '', 0, winreg.REG_SZ, str(path))
        written.append(str(path))
    else:
        for folder in target_dirs or linux_manifest_dirs():
            folder = Path(folder)
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f'{HOST_NAME}.json').write_text(data, encoding='utf-8')
            written.append(str(folder / f'{HOST_NAME}.json'))
    return written


def uninstall(target_dirs=None):
    if sys.platform == 'win32' and not target_dirs:
        import winreg
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REG_KEY)
        except FileNotFoundError:
            pass
        paths = [config.config_dir() / f'{HOST_NAME}.json']
    else:
        paths = [Path(d) / f'{HOST_NAME}.json' for d in (target_dirs or linux_manifest_dirs())]
    for p in paths:
        if p.exists():
            os.remove(p)
