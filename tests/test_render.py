"""Real FFmpeg integration tests; no external model, paid API or user footage."""
import io
import os
import subprocess
import time
import zipfile

os.environ.setdefault('APP_ENV', 'local')

import pytest
from fastapi.testclient import TestClient
from server import app as module, core, media

HEADERS = {'x-video-factory': '1'}


def make_video(path, color='red', audio=True):
    args = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'lavfi',
            '-i', f'color=c={color}:s=160x240:r=24:d=0.30']
    if audio:
        args += ['-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=0.30']
    args += ['-t', '0.30', '-c:v', 'libx264', '-threads', '1', '-pix_fmt', 'yuv420p']
    if audio:
        args += ['-c:a', 'aac']
    subprocess.run(args + [str(path)], check=True, timeout=30, capture_output=True)


@pytest.fixture
def studio(tmp_path, monkeypatch):
    root = tmp_path / 'private'
    monkeypatch.setattr(core, 'ROOT', root)
    monkeypatch.setattr(core, 'DB', root / 'db.sqlite3')
    monkeypatch.setattr(media, 'ROOT', root)
    monkeypatch.setattr(module, 'LOCAL', True)
    source = tmp_path / 'source.mp4'
    silent = tmp_path / 'silent.mp4'
    make_video(source)
    make_video(silent, color='blue', audio=False)
    with TestClient(module.app) as client:
        p = client.post('/api/projects', headers=HEADERS, json={'name': 'Integration test'})
        assert p.status_code == 200, p.text
        yield client, p.json()['id'], source.read_bytes(), silent.read_bytes()


def upload(client, pid, kind, content, name='clip.mp4'):
    result = client.post(f'/api/projects/{pid}/uploads', headers=HEADERS,
                         json={'name': name, 'size': len(content), 'kind': kind})
    assert result.status_code == 200, result.text
    aid = result.json()['id']
    midpoint = len(content) // 2
    for start, stop in ((0, midpoint), (midpoint, len(content))):
        result = client.patch(f'/api/uploads/{aid}',
                              headers={**HEADERS, 'upload-offset': str(start), 'content-type': 'application/octet-stream'},
                              content=content[start:stop])
        assert result.status_code == 200, result.text
        assert result.json()['received'] == stop
    result = client.post(f'/api/uploads/{aid}/finish', headers=HEADERS)
    assert result.status_code == 200, result.text
    return aid


def wait_job(client, jid):
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        result = client.get(f'/api/jobs/{jid}').json()
        if result['status'] in ('completed', 'failed', 'cancelled'):
            assert result['status'] == 'completed', result.get('error') or result
            return result
        time.sleep(0.10)
    pytest.fail('Render did not finish within test timeout')


@pytest.mark.parametrize('template', ['solo', 'stack', 'side', 'pip', 'chroma', 'card'])
def test_each_template_exports_real_mp4(studio, template):
    client, pid, source, silent = studio
    for kind in ('hook', 'body', 'cta'):
        upload(client, pid, kind, silent if kind == 'cta' else source)
    upload(client, pid, 'support', silent)
    body = {'count': 1, 'seed': 5, 'request_id': f'test-{template}-001',
            'settings': {'template': template, 'resolution': '360', 'normalize_audio': False,
                         'captions': 'off', 'title': 'Teste de exportação', 'signature': 'Sol'}}
    result = client.post(f'/api/projects/{pid}/jobs', headers=HEADERS, json=body)
    assert result.status_code == 200, result.text
    job = wait_job(client, result.json()['id'])
    assert len(job['outputs']) == 1
    output = job['outputs'][0]
    assert (output['width'], output['height']) == (360, 640)
    assert output['duration'] > 0.5 and output['bytes'] > 1000
    download = client.get(f'/api/jobs/{job["id"]}/files/{output["file"]}')
    assert download.status_code == 200 and download.content[4:8] == b'ftyp'


def test_15_unique_outputs_and_zip(studio):
    client, pid, source, silent = studio
    for kind, count in (('hook', 5), ('body', 3), ('cta', 5)):
        for index in range(count):
            upload(client, pid, kind, source, f'{kind}-{index}.mp4')
    body = {'count': 15, 'seed': 8, 'request_id': 'test-batch-0001',
            'settings': {'template': 'solo', 'resolution': '360', 'normalize_audio': False, 'captions': 'off'}}
    result = client.post(f'/api/projects/{pid}/jobs', headers=HEADERS, json=body)
    assert result.status_code == 200, result.text
    jid = result.json()['id']
    # Idempotent requests must return the same job, not create duplicate renders.
    repeated = client.post(f'/api/projects/{pid}/jobs', headers=HEADERS, json=body)
    assert repeated.status_code == 200 and repeated.json()['id'] == jid
    job = wait_job(client, jid)
    assert job['possible'] == 75 and len(job['outputs']) == 15
    assert len({tuple(v) for v in job['variations']}) == 15
    result = client.get(f'/api/jobs/{jid}/files/videos.zip')
    assert result.status_code == 200
    with zipfile.ZipFile(io.BytesIO(result.content)) as archive:
        assert len([p for p in archive.namelist() if p.endswith('.mp4')]) == 15
        assert 'manifesto.json' in archive.namelist()


def test_full_hd_output(studio):
    client, pid, source, silent = studio
    for kind in ('hook', 'body', 'cta'):
        upload(client, pid, kind, source)
    body = {'count': 1, 'seed': 4, 'request_id': 'test-fullhd-0001',
            'settings': {'resolution': '1080', 'normalize_audio': False, 'captions': 'off'}}
    result = client.post(f'/api/projects/{pid}/jobs', headers=HEADERS, json=body)
    assert result.status_code == 200, result.text
    job = wait_job(client, result.json()['id'])
    assert (job['outputs'][0]['width'], job['outputs'][0]['height']) == (1080, 1920)
