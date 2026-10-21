"""Folder and file naming. Nothing here ever deletes or overwrites a file."""

import os
import re
from pathlib import Path

_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}


def sanitize(name, max_len=80):
    """Make a string safe as a Windows folder/file name."""
    name = _INVALID.sub(' ', str(name))
    name = re.sub(r'\s+', ' ', name).strip().rstrip('. ')
    name = name[:max_len].rstrip('. ')
    if not name:
        name = 'images'
    if name.upper() in _RESERVED:
        name += '_'
    return name


def existing_numbers(folder, prefix):
    pattern = re.compile(rf'^{re.escape(prefix)}_(\d+)\.png$', re.IGNORECASE)
    folder = Path(folder)
    if not folder.is_dir():
        return []
    return sorted(int(m.group(1)) for f in folder.iterdir() if (m := pattern.match(f.name)))


def folder_status(base, name):
    """What is already in <base>/<name>: used by the popup to warn before saving."""
    name = sanitize(name)
    folder = Path(base) / name
    nums = existing_numbers(folder, name)
    return {
        'name': name,
        'path': str(folder),
        'exists': folder.exists(),
        'count': len(nums),
        'next': (max(nums) + 1) if nums else 1,
    }


def unique_folder(base, name):
    """<name>, or '<name> (2)', '<name> (3)'... - the first that doesn't exist."""
    name = sanitize(name)
    candidate, n = name, 2
    while (Path(base) / candidate).exists():
        candidate = f'{name} ({n})'
        n += 1
    return candidate


def file_name(prefix, number):
    return f'{prefix}_{number}.png'


def write_new(path, data):
    """Write bytes atomically; refuse to overwrite an existing file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.part')
    tmp.write_bytes(data)
    try:
        if path.exists():
            raise FileExistsError(path)
        os.rename(tmp, path)  # os.rename refuses to replace on Windows
    finally:
        if tmp.exists():
            tmp.unlink()
