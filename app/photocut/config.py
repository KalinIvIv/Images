"""Per-user settings stored in %APPDATA%\\PhotoCut\\config.json (~/.config/photocut elsewhere)."""

import json
import os
import sys
from pathlib import Path

DEFAULTS = {
    'base_folder': str(Path.home() / 'Pictures' / 'PhotoCut'),
    'rules_path': '',          # shared rules.json, e.g. in a Google Drive for desktop folder
    'user_name': os.environ.get('USERNAME') or os.environ.get('USER') or '',
    'open_folder': True,       # open Explorer when a job finishes
    'flatten': False,          # put transparent images on white
    'tolerance': 30,
}


def config_dir():
    override = os.environ.get('PHOTOCUT_CONFIG_DIR')
    if override:
        return Path(override)
    if sys.platform == 'win32':
        return Path(os.environ.get('APPDATA', Path.home())) / 'PhotoCut'
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'photocut'


def config_path():
    return config_dir() / 'config.json'


def load():
    cfg = dict(DEFAULTS)
    try:
        with open(config_path(), encoding='utf-8') as f:
            cfg.update({k: v for k, v in json.load(f).items() if k in DEFAULTS})
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as e:
        print(f'Could not read config: {e}', file=sys.stderr)
    return cfg


def save(changes):
    cfg = load()
    cfg.update({k: v for k, v in changes.items() if k in DEFAULTS})
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(cfg, indent=2), encoding='utf-8')
    os.replace(tmp, path)
    return cfg
