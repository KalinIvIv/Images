import base64
import io
import json
import os
import struct
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

APP = Path(__file__).resolve().parent.parent


class HostProcess:
    """Talks to `python -m photocut chrome-extension://...` exactly like Chrome does."""

    def __init__(self, env):
        self.p = subprocess.Popen([sys.executable, '-m', 'photocut', 'chrome-extension://test/'],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  env={**os.environ, 'PYTHONPATH': str(APP), **env})

    def send(self, msg):
        data = json.dumps(msg).encode()
        self.p.stdin.write(struct.pack('@I', len(data)) + data)
        self.p.stdin.flush()

    def recv(self):
        (n,) = struct.unpack('@I', self.p.stdout.read(4))
        return json.loads(self.p.stdout.read(n))

    def until(self, pred):
        while True:
            msg = self.recv()
            if pred(msg):
                return msg

    def close(self):
        self.p.stdin.close()
        assert self.p.wait(10) == 0, self.p.stderr.read().decode()


def jpeg(color, size=(900, 700)):
    img = Image.new('RGB', size, 'white')
    ImageDraw.Draw(img).rectangle((200, 150, 500, 450), fill=color)
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=95)
    return base64.b64encode(buf.getvalue()).decode()


def test_host_round_trip(tmp_path):
    base = tmp_path / 'out'
    shared = tmp_path / 'drive' / 'rules.json'
    h = HostProcess({'PHOTOCUT_CONFIG_DIR': str(tmp_path / 'cfg')})

    h.send({'id': 1, 'type': 'set_config', 'config': {
        'base_folder': str(base), 'rules_path': str(shared), 'user_name': 'Kalin', 'open_folder': False}})
    assert h.recv()['config']['base_folder'] == str(base)

    h.send({'id': 2, 'type': 'ping'})
    assert h.recv()['ok']

    h.send({'id': 3, 'type': 'save_rule', 'domain': 'www.lg.com', 'rule': {'gallery': '.pdp-gallery'}})
    assert h.recv()['rules']['sites']['lg.com']['updatedBy'] == 'Kalin'
    h.send({'id': 4, 'type': 'get_rules'})
    assert h.recv()['rules']['sites']['lg.com']['gallery'] == '.pdp-gallery'

    h.send({'id': 5, 'type': 'folder_status', 'folder': 'Monitor: 32GS95UV'})
    st = h.recv()
    assert st['name'] == 'Monitor 32GS95UV' and not st['exists']

    # A job: 3 images streamed in, one failed download, sent out of order.
    h.send({'id': 6, 'type': 'job_start', 'jobId': 'j1', 'folder': 'Monitor 32GS95UV', 'total': 4})
    assert h.recv()['folder'] == str(base / 'Monitor 32GS95UV')
    h.send({'type': 'job_image', 'jobId': 'j1', 'index': 2, 'data': jpeg('green'), 'url': 'c'})
    h.send({'type': 'job_image', 'jobId': 'j1', 'index': 0, 'data': jpeg('red'), 'url': 'a'})
    h.send({'type': 'job_image', 'jobId': 'j1', 'index': 1, 'error': 'HTTP 403', 'url': 'b'})
    h.send({'type': 'job_image', 'jobId': 'j1', 'index': 3, 'data': base64.b64encode(b'not an image').decode(), 'url': 'd'})
    h.send({'type': 'job_end', 'jobId': 'j1'})
    done = h.until(lambda m: m.get('type') == 'job_done')

    assert [s['file'] for s in done['saved']] == ['Monitor 32GS95UV_1.png', 'Monitor 32GS95UV_2.png']
    assert len(done['errors']) == 2 and 'HTTP 403' in done['errors'][0]
    first = Image.open(base / 'Monitor 32GS95UV' / 'Monitor 32GS95UV_1.png').convert('RGB')
    r, g, _ = first.getpixel((first.width // 2, first.height // 2))
    assert r > 200 and g < 60  # the red image (index 0) is number 1

    # Same folder again in "add" mode continues numbering; "new" makes "(2)".
    h.send({'id': 7, 'type': 'job_start', 'jobId': 'j2', 'folder': 'Monitor 32GS95UV', 'total': 1})
    h.recv()
    h.send({'type': 'job_image', 'jobId': 'j2', 'index': 0, 'data': jpeg('blue'), 'url': 'e'})
    h.send({'type': 'job_end', 'jobId': 'j2'})
    assert h.until(lambda m: m.get('type') == 'job_done')['saved'][0]['file'] == 'Monitor 32GS95UV_3.png'

    h.send({'id': 8, 'type': 'job_start', 'jobId': 'j3', 'folder': 'Monitor 32GS95UV', 'mode': 'new', 'total': 1})
    assert h.recv()['folder'].endswith('Monitor 32GS95UV (2)')
    h.send({'type': 'job_image', 'jobId': 'j3', 'index': 0, 'data': jpeg('blue'), 'url': 'e'})
    h.send({'type': 'job_end', 'jobId': 'j3'})
    assert h.until(lambda m: m.get('type') == 'job_done')['saved'][0]['file'] == 'Monitor 32GS95UV_1.png'

    h.send({'id': 9, 'type': 'nonsense'})
    assert h.recv() == {'id': 9, 'ok': False, 'error': 'Unknown request: nonsense'}
    h.close()


def test_install_writes_manifest(tmp_path):
    env = {**os.environ, 'PYTHONPATH': str(APP), 'PHOTOCUT_CONFIG_DIR': str(tmp_path / 'cfg')}
    code = ('from photocut import install; '
            f'print(install.install([r"{tmp_path / "hosts"}"]))')
    subprocess.run([sys.executable, '-c', code], check=True, env=env)
    m = json.loads((tmp_path / 'hosts' / 'com.photocut.host.json').read_text())
    assert m['allowed_origins'] == ['chrome-extension://dhmhjgdnpjnnfpajmflglfajjmofnjmg/']
    assert Path(m['path']).exists()
