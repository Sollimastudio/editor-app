import os
os.environ.setdefault('APP_ENV','local')
import pytest
from fastapi.testclient import TestClient
from server import app as module,core,media

@pytest.fixture
def client(tmp_path,monkeypatch):
 monkeypatch.setattr(core,'ROOT',tmp_path);monkeypatch.setattr(core,'DB',tmp_path/'db.sqlite3');monkeypatch.setattr(media,'ROOT',tmp_path)
 monkeypatch.setattr(module,'LOCAL',True)
 with TestClient(module.app) as c:yield c

def test_csrf_protection(client):
 assert client.post('/api/projects',json={'name':'test'}).status_code==403

def test_persist_project_and_settings(client):
 p=client.post('/api/projects',headers={'x-video-factory':'1'},json={'name':'teste'}).json()
 assert client.get('/api/projects/'+p['id']).json()['name']=='teste'
 r=client.put('/api/projects/'+p['id']+'/settings',headers={'x-video-factory':'1'},json={'template':'stack'})
 assert r.status_code==200
 assert client.get('/api/projects/'+p['id']).json()['settings']['template']=='stack'

def test_unavailable_ai_not_fake_success(client):
 s=client.get('/api/status').json()
 assert s['lip_sync'] is False and s['face_tracking'] is False

def test_path_traversal_and_invalid_id(client):
 assert client.get('/api/assets/invalid/media').status_code==400
 assert client.get('/data/factory.sqlite3').status_code==404

def test_missing_buckets_render_rejected(client):
 headers={'x-video-factory':'1'}
 p=client.post('/api/projects',headers=headers,json={'name':'x'}).json()
 assert client.post('/api/projects/'+p['id']+'/plan',headers=headers,json={'count':15}).status_code==400

def test_authentication_is_required_in_production(tmp_path,monkeypatch):
 monkeypatch.setattr(core,'ROOT',tmp_path);monkeypatch.setattr(core,'DB',tmp_path/'db.sqlite3');monkeypatch.setattr(media,'ROOT',tmp_path)
 monkeypatch.setattr(module,'LOCAL',False);monkeypatch.setattr(module,'PASSWORD','long-enough-test-password');monkeypatch.setattr(module,'SECRET','test-secret-012345678901234567890123456789')
 with TestClient(module.app,base_url='https://testserver') as c:
  assert c.get('/api/projects').status_code==401
  assert c.post('/api/login',headers={'x-video-factory':'1'},json={'password':'wrong'}).status_code==401
  login=c.post('/api/login',headers={'x-video-factory':'1'},json={'password':'long-enough-test-password'})
  assert login.status_code==200
  cookie=login.headers['set-cookie'].lower();assert 'httponly' in cookie and 'secure' in cookie and 'samesite=strict' in cookie
  assert c.get('/api/projects').status_code==200

def test_production_refuses_missing_secrets(tmp_path,monkeypatch):
 monkeypatch.setattr(module,'LOCAL',False);monkeypatch.setattr(module,'PASSWORD','');monkeypatch.setattr(module,'SECRET','')
 with pytest.raises(RuntimeError):
  with TestClient(module.app):pass
