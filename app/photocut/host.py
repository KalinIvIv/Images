"""
Chrome native messaging host.

Chrome starts this program when the extension connects, and talks to it over
stdin/stdout: each message is a 4-byte length (native byte order) + UTF-8 JSON.

Requests from the extension carry an "id"; the reply echoes it.
Job messages (job_start / job_image / job_end) stream images in; the host sends
"progress" and "job_done" events back while processing them in parallel.
"""

import base64
import json
import os
import struct
import subprocess
import sys
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import __version__, config, naming, pipeline, rules


def open_in_explorer(path):
    if sys.platform == 'win32':
        os.startfile(path)  # noqa: S606 - opening the user's own output folder
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', path])
    else:
        subprocess.Popen(['xdg-open', path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def ask_path(kind, initial=''):
    """Native folder/file picker shown on top of Chrome."""
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    initial_dir = initial if os.path.isdir(initial) else os.path.dirname(initial) or None
    try:
        if kind == 'folder':
            return filedialog.askdirectory(parent=root, initialdir=initial_dir, title='Choose folder') or ''
        return filedialog.asksaveasfilename(
            parent=root, initialdir=initial_dir, initialfile='rules.json', title='Shared rules file',
            defaultextension='.json', filetypes=[('PhotoCut rules', '*.json')], confirmoverwrite=False) or ''
    finally:
        root.destroy()


class Job:
    def __init__(self, folder, prefix, start_number, total):
        self.folder = folder
        self.prefix = prefix
        self.start_number = start_number
        self.total = total
        self.results = {}   # index -> (png bytes, info)
        self.errors = {}    # index -> message
        self.pending = 0
        self.ended = False
        self.lock = threading.Lock()


class Host:
    def __init__(self, stdin=None, stdout=None, workers=None):
        self.stdin = stdin or sys.stdin.buffer
        self.stdout = stdout or sys.stdout.buffer
        self.write_lock = threading.Lock()
        self.pool = ThreadPoolExecutor(workers or max(2, os.cpu_count() or 2))
        self.misc = ThreadPoolExecutor(2)
        self.jobs = {}

    # --- transport ------------------------------------------------------------

    def read(self):
        header = self.stdin.read(4)
        if len(header) < 4:
            return None
        (length,) = struct.unpack('@I', header)
        return json.loads(self.stdin.read(length).decode('utf-8'))

    def send(self, msg):
        data = json.dumps(msg).encode('utf-8')
        with self.write_lock:
            self.stdout.write(struct.pack('@I', len(data)) + data)
            self.stdout.flush()

    def run(self):
        while (msg := self.read()) is not None:
            kind = msg.get('type')
            if kind in ('job_start', 'job_image', 'job_end'):
                self.safe(msg, getattr(self, kind))   # order matters, and these are quick
            else:
                self.misc.submit(self.safe, msg, self.handle)
        self.pool.shutdown(wait=True)
        self.misc.shutdown(wait=True)

    def safe(self, msg, fn):
        try:
            result = fn(msg)
            if result is not None and 'id' in msg:
                self.send({'id': msg['id'], 'ok': True, **result})
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            if 'id' in msg:
                self.send({'id': msg['id'], 'ok': False, 'error': str(e)})

    # --- simple requests --------------------------------------------------------

    def handle(self, msg):
        kind = msg.get('type')
        cfg = config.load()

        if kind == 'ping':
            return {'version': __version__, 'config': cfg}
        if kind == 'get_config':
            return {'config': cfg}
        if kind == 'set_config':
            return {'config': config.save(msg.get('config', {}))}
        if kind == 'get_rules':
            try:
                return {'rules': rules.load(cfg['rules_path']), 'path': cfg['rules_path']}
            except (OSError, ValueError) as e:
                return {'rules': rules.empty(), 'path': cfg['rules_path'], 'warning': str(e)}
        if kind == 'save_rule':
            if not cfg['rules_path']:
                raise ValueError('No shared rules file set. Open PhotoCut options to choose one.')
            data = rules.save_site(cfg['rules_path'], msg['domain'], msg.get('rule'), cfg['user_name'])
            return {'rules': data}
        if kind == 'folder_status':
            return naming.folder_status(cfg['base_folder'], msg.get('folder', ''))
        if kind == 'pick_path':
            return {'path': ask_path(msg.get('kind', 'folder'), msg.get('initial', ''))}
        if kind == 'open_folder':
            open_in_explorer(msg.get('path') or cfg['base_folder'])
            return {}
        raise ValueError(f'Unknown request: {kind}')

    # --- jobs -------------------------------------------------------------------

    def job_start(self, msg):
        cfg = config.load()
        base = cfg['base_folder']
        prefix = naming.sanitize(msg['folder'])
        name = naming.unique_folder(base, prefix) if msg.get('mode') == 'new' else prefix
        status = naming.folder_status(base, name)
        job = Job(Path(base) / name, prefix, status['next'] if name == prefix else 1, msg.get('total', 0))
        job.settings = pipeline.Settings(tolerance=int(cfg['tolerance']), flatten=bool(cfg['flatten']))
        job.open_folder = cfg['open_folder']
        self.jobs[msg['jobId']] = job
        return {'folder': str(job.folder)}

    def job_image(self, msg):
        job = self.jobs[msg['jobId']]
        index = msg['index']
        if msg.get('error') or not msg.get('data'):
            with job.lock:
                job.errors[index] = f"{msg.get('url', '')}: {msg.get('error') or 'no data'}"
            self.progress(msg['jobId'], job)
            return None
        with job.lock:
            job.pending += 1
        self.pool.submit(self.process_one, msg['jobId'], job, index, base64.b64decode(msg['data']), msg.get('url', ''))
        return None

    def process_one(self, job_id, job, index, data, url):
        try:
            result = pipeline.process(data, job.settings)
            with job.lock:
                job.results[index] = result
        except Exception as e:
            with job.lock:
                job.errors[index] = f'{url}: {e}'
        with job.lock:
            job.pending -= 1
        self.progress(job_id, job)
        self.maybe_finish(job_id, job)

    def progress(self, job_id, job):
        with job.lock:
            done = len(job.results) + len(job.errors)
        self.send({'type': 'progress', 'jobId': job_id, 'done': done, 'total': job.total})

    def job_end(self, msg):
        job = self.jobs[msg['jobId']]
        with job.lock:
            job.ended = True
        self.maybe_finish(msg['jobId'], job)
        return None

    def maybe_finish(self, job_id, job):
        with job.lock:
            if not job.ended or job.pending or job_id not in self.jobs:
                return
            del self.jobs[job_id]

        # Number the successful images consecutively, in gallery order.
        saved, number = [], job.start_number
        for index in sorted(job.results):
            data, info = job.results[index]
            while True:
                path = job.folder / naming.file_name(job.prefix, number)
                number += 1
                try:
                    naming.write_new(path, data)
                    break
                except FileExistsError:
                    continue
            saved.append({'file': path.name, 'size': info['final'], 'bytes': info['bytes'],
                          'overLimit': info['over_limit']})

        errors = [job.errors[i] for i in sorted(job.errors)]
        self.send({'type': 'job_done', 'jobId': job_id, 'folder': str(job.folder),
                   'saved': saved, 'errors': errors})
        if saved and job.open_folder:
            try:
                open_in_explorer(str(job.folder))
            except OSError:
                pass


def main():
    if sys.platform == 'win32':
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    Host().run()
