"""Persistent single-user video factory. No uploaded media is executed as code."""
from __future__ import annotations
import hashlib, itertools, json, math, os, random, re, sqlite3, threading, time, uuid
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

ROOT = Path(os.getenv('DATA_DIR', './data')).resolve()
DB = ROOT / 'factory.sqlite3'
LOCK = threading.RLock()
KINDS = ('hook', 'body', 'cta', 'support', 'music')
MAX_UPLOAD = int(os.getenv('MAX_UPLOAD_MB', '500')) * 1024 * 1024
MAX_STORAGE = int(os.getenv('MAX_STORAGE_MB', '10000')) * 1024 * 1024

class Settings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    template: Literal['solo','stack','side','pip','chroma','card'] = 'solo'
    resolution: Literal['360','720','1080'] = '1080'
    trim_silence: bool = False
    normalize_audio: bool = True
    captions: Literal['off','import','auto'] = 'import'
    fit: Literal['contain','cover'] = 'contain'
    gentle_zoom: bool = False
    title: str = Field(default='', max_length=110)
    signature: str = Field(default='', max_length=40)
    caption_color: str = Field(default='#ffffff', pattern=r'^#[0-9A-Fa-f]{6}$')
    chroma_color: str = Field(default='#00ff00', pattern=r'^#[0-9A-Fa-f]{6}$')
    chroma_similarity: float = Field(default=.22, ge=.01, le=.6)
    music_volume: float = Field(default=.10, ge=0, le=.5)
    max_seconds: int = Field(default=180, ge=3, le=600)

class PlanRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    count: int = Field(default=15, ge=1, le=50)
    seed: int = Field(default=42, ge=0, le=2**32-1)
    settings: Settings = Field(default_factory=Settings)

class Cue(BaseModel):
    start: float = Field(ge=0, le=7200, allow_inf_nan=False)
    end: float = Field(gt=0, le=7200, allow_inf_nan=False)
    text: str = Field(min_length=1, max_length=300)

def ident() -> str:
    return str(uuid.uuid4())

def valid_id(value: str) -> str:
    if not re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', value):
        raise ValueError('Identificador inválido.')
    return value

def initialize():
    for name in ('uploads','cache','jobs'):
        (ROOT/name).mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE IF NOT EXISTS records (kind TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(kind,id))')

def connect():
    db = sqlite3.connect(DB, timeout=30)
    db.execute('PRAGMA busy_timeout=30000')
    return db

def put(kind: str, item: dict):
    with LOCK, connect() as db:
        db.execute('INSERT INTO records VALUES(?,?,?) ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data',
                   (kind, item['id'], json.dumps(item, ensure_ascii=False, allow_nan=False)))
    return item

def get(kind: str, item_id: str) -> dict:
    valid_id(item_id)
    with connect() as db:
        row = db.execute('SELECT data FROM records WHERE kind=? AND id=?',(kind,item_id)).fetchone()
    if not row:
        raise KeyError('Item não encontrado.')
    return json.loads(row[0])

def records(kind: str, project: str | None = None) -> list[dict]:
    with connect() as db:
        result = [json.loads(row[0]) for row in db.execute('SELECT data FROM records WHERE kind=? ORDER BY rowid', (kind,))]
    return [x for x in result if project is None or x.get('project') == project]

def remove(kind: str, item_id: str):
    with LOCK, connect() as db:
        db.execute('DELETE FROM records WHERE kind=? AND id=?',(kind,item_id))

def patch(kind: str, item_id: str, **values):
    with LOCK:
        item = get(kind,item_id)
        item.update(values)
        return put(kind,item)

def asset_path(asset: dict) -> Path:
    return ROOT / 'uploads' / (valid_id(asset['id']) + asset['ext'])

def digest(path: Path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()

def plan(assets: list[dict], count: int, seed: int, max_seconds: int) -> dict:
    groups = [[a for a in assets if a['kind']==kind and a.get('status')=='ready'] for kind in ('hook','body','cta')]
    if not all(groups):
        raise ValueError('Adicione pelo menos uma abertura, um conteúdo e um encerramento.')
    total = math.prod(len(g) for g in groups)
    if total > 100000:
        raise ValueError('Há mais de 100 mil combinações. Divida os arquivos em projetos menores.')
    def duration(a):
        return (a.get('trim_end') or a['duration']) - a.get('trim_start',0)
    pool = [p for p in itertools.product(*groups) if sum(duration(a) for a in p) <= max_seconds]
    available = len(pool)
    if not pool:
        raise ValueError('Todas as combinações excedem a duração máxima. Ajuste o limite ou corte os clipes.')
    rng = random.Random(seed)
    rng.shuffle(pool)
    uses = [{a['id']:0 for a in g} for g in groups]
    chosen = []
    adjacent = 0
    for _ in range(min(count,available)):
        previous = chosen[-1] if chosen else []
        def cost(p):
            return sum(uses[i][a['id']]*10 + (1000 if previous and previous[i]['id']==a['id'] and len(groups[i])>1 else 0) for i,a in enumerate(p))
        best = min(range(len(pool)),key=lambda i: cost(pool[i]))
        selected = pool.pop(best)
        if previous:
            adjacent += sum(a['id']==previous[i]['id'] and len(groups[i])>1 for i,a in enumerate(selected))
        for i,a in enumerate(selected): uses[i][a['id']] += 1
        chosen.append(selected)
    warnings=[]
    if count>available: warnings.append(f'Existem {available} combinações válidas; o lote foi limitado a esse número.')
    if adjacent: warnings.append('Algumas repetições consecutivas foram necessárias. Nenhuma combinação completa foi duplicada.')
    return {'variations':[[a['id'] for a in p] for p in chosen], 'possible':total,
            'available':available,'warnings':warnings,'usage':uses}
