"""
Command line, for setup and for use without Chrome:

  PhotoCut install | uninstall
  PhotoCut folder <input folder> <output folder name>       crop images already on disk
  PhotoCut urls <output folder name> <image url> [...]       download and crop
  (add --no-trim to keep whole images: only resize, pad and save as PNG)
  PhotoCut config [key=value ...]                           show or change settings
"""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import config, install, naming, pipeline

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.jfif', '.png', '.webp', '.bmp', '.tif', '.tiff', '.avif', '.gif'}


def download(url, referer=None, timeout=20):
    import requests
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                             '(KHTML, like Gecko) Chrome/130.0 Safari/537.36'}
    if referer:
        headers['Referer'] = referer
    last = None
    for _ in range(3):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            r.raise_for_status()
            return r.content
        except requests.RequestException as e:
            last = e
    raise last


def save_all(sources, folder_name, load, trim=True):
    """Process sources in parallel, save as <name>_N.png in input order."""
    cfg = config.load()
    settings = pipeline.Settings(tolerance=int(cfg['tolerance']), flatten=bool(cfg['flatten']))
    prefix = naming.sanitize(folder_name)
    status = naming.folder_status(cfg['base_folder'], prefix)
    folder, number = Path(status['path']), status['next']

    def work(src):
        return pipeline.process(load(src), settings, trim=trim)

    with ThreadPoolExecutor() as pool:
        futures = [pool.submit(work, s) for s in sources]
    for src, fut in zip(sources, futures):
        try:
            data, info = fut.result()
        except Exception as e:
            print(f'FAILED {src}: {e}')
            continue
        path = folder / naming.file_name(prefix, number)
        number += 1
        naming.write_new(path, data)
        print(f'{path}  {info["final"][0]}x{info["final"][1]}  {info["bytes"] / 1048576:.2f}MB')
    return folder


def main(argv=None):
    p = argparse.ArgumentParser(prog='PhotoCut', description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('install')
    sub.add_parser('uninstall')
    f = sub.add_parser('folder')
    f.add_argument('input')
    f.add_argument('name')
    f.add_argument('--no-trim', action='store_true', help='keep whole images (only resize and pad)')
    u = sub.add_parser('urls')
    u.add_argument('name')
    u.add_argument('urls', nargs='+')
    u.add_argument('--referer')
    u.add_argument('--no-trim', action='store_true', help='keep whole images (only resize and pad)')
    c = sub.add_parser('config')
    c.add_argument('changes', nargs='*', metavar='key=value')
    args = p.parse_args(argv)

    if args.cmd == 'install':
        for path in install.install():
            print(f'Registered Chrome host: {path}')
    elif args.cmd == 'uninstall':
        install.uninstall()
        print('Unregistered.')
    elif args.cmd == 'folder':
        files = sorted(f for f in Path(args.input).iterdir() if f.suffix.lower() in IMAGE_EXTENSIONS)
        print(f'Saved to {save_all(files, args.name, Path.read_bytes, trim=not args.no_trim)}')
    elif args.cmd == 'urls':
        print(f'Saved to {save_all(args.urls, args.name, lambda u: download(u, args.referer), trim=not args.no_trim)}')
    elif args.cmd == 'config':
        changes = {}
        for item in args.changes:
            key, _, value = item.partition('=')
            default = config.DEFAULTS.get(key)
            if isinstance(default, bool):
                value = value.lower() in ('1', 'true', 'yes')
            elif isinstance(default, int):
                value = int(value)
            changes[key] = value
        cfg = config.save(changes) if changes else config.load()
        for k, v in cfg.items():
            print(f'{k} = {v}')


if __name__ == '__main__':
    sys.exit(main())
