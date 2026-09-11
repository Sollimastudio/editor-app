"""HTTP API + durable, single-worker queue. Run ONE instance with ONE uvicorn worker."""
from __future__ import annotations
import asyncio, hashlib, hmac, importlib.util, json, os, secrets, shutil, threading, time, zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from . import core as db
from . import media

STOP=threading.Event()
WAKE=threading.Event()
LOCAL=os.getenv('APP_ENV')=='local'
PASSWORD=os.getenv('APP_PASSWORD','')
SECRET=os.getenv('SESSION_SECRET','')
ATTEMPTS={}
STUDIO=Path(__file__).resolve().parent.parent/'studio'


def active(project):
    return any(j['status'] in ('queued','processing') for j in db.records('job',project))

def process_job(job):
    jid=job['id']; directory=db.ROOT/'jobs'/jid; directory.mkdir(exist_ok=True)
    settings=db.Settings(**job['settings'])
    assets={a['id']:a for a in job['assets']}
    supports=[a for a in job['assets'] if a['kind']=='support']
    music=next((a for a in job['assets'] if a['kind']=='music'),None)
    def cancelled():
        return STOP.is_set() or db.get('job',jid).get('cancel',False)
    outputs=list(job.get('outputs',[]))
    db.patch('job',jid,status='processing',message='Preparando os clipes',error=None)
    try:
        if cancelled(): raise media.Cancelled()
        prepared={}
        required=list(dict.fromkeys(a for seq in job['variations'] for a in seq))
        for idx,aid in enumerate(required):
            if cancelled(): raise media.Cancelled()
            db.patch('job',jid,message=f'Preparando clipe {idx+1} de {len(required)}',progress=round(20*idx/len(required)))
            prepared[aid]=media.prepare(assets[aid],settings,cancelled)
        for index,seq in enumerate(job['variations']):
            if cancelled(): raise media.Cancelled()
            filename=f'video-{index+1:02d}.mp4'; path=directory/filename
            existing=next((o for o in outputs if o['file']==filename),None)
            if existing and path.exists(): continue
            db.patch('job',jid,message=f'Exportando vídeo {index+1} de {len(job["variations"])}',progress=20+round(75*index/len(job['variations'])))
            support=supports[index%len(supports)] if supports else None
            info=media.compose([prepared[a] for a in seq],support,music,settings,path,cancelled)
            outputs=[o for o in outputs if o['file']!=filename]
            outputs.append({'file':filename,'duration':info['duration'],'width':info['width'],'height':info['height'],'bytes':path.stat().st_size,
                            'clips':[assets[a]['name'] for a in seq],'sha256':db.digest(path)})
            db.patch('job',jid,outputs=outputs)
        if cancelled(): raise media.Cancelled()
        with zipfile.ZipFile(directory/'videos.partial.zip','w',zipfile.ZIP_STORED) as archive:
            for result in outputs: archive.write(directory/result['file'],result['file'])
            archive.writestr('manifesto.json',json.dumps({'settings':job['settings'],'outputs':outputs,'warnings':job['warnings']},ensure_ascii=False,indent=2))
        (directory/'videos.partial.zip').replace(directory/'videos.zip')
        db.patch('job',jid,status='completed',progress=100,message='Vídeos prontos',finished=time.time())
    except media.Cancelled:
        db.patch('job',jid,status='queued' if STOP.is_set() else 'cancelled',message='Interrompido; os arquivos concluídos foram preservados.')
    except Exception as exc:
        # Detailed diagnostics remain in a protected record; there are no API keys in render commands.
        db.patch('job',jid,status='failed',message='Não foi possível concluir este lote.',error=str(exc)[-1800:])

def worker():
    while not STOP.is_set():
        with db.LOCK:
            jobs=[j for j in db.records('job') if j['status']=='queued']
            job=jobs[0] if jobs else None
        if job: process_job(job)
        else: WAKE.wait(1); WAKE.clear()

@asynccontextmanager
async def lifespan(app):
    if not LOCAL and (len(PASSWORD)<16 or len(SECRET)<32):
        raise RuntimeError('Defina APP_PASSWORD (16+ caracteres) e SESSION_SECRET (32+) antes de publicar. Modo local: APP_ENV=local em 127.0.0.1.')
    db.initialize(); STOP.clear()
    for asset in db.records('asset'):
        if asset['status']=='processing': db.patch('asset',asset['id'],status='uploading')
    for job in db.records('job'):
        if job['status']=='processing': db.patch('job',job['id'],status='queued',message='Retomando após reinício')
    thread=threading.Thread(target=worker,daemon=True,name='video-worker'); thread.start()
    try: yield
    finally: STOP.set(); WAKE.set(); thread.join(timeout=8)

app=FastAPI(title='Sol Video Factory',version='0.2.0',lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)

@app.exception_handler(KeyError)
async def not_found(_request, _exc): return JSONResponse({'detail':'Item não encontrado.'},404)
@app.exception_handler(ValueError)
async def invalid(_request, exc): return JSONResponse({'detail':str(exc)},400)

@app.middleware('http')
async def protections(request:Request,call_next):
    if request.url.path.startswith('/api/') and request.method not in ('GET','HEAD','OPTIONS'):
        if request.headers.get('x-video-factory')!='1':
            return JSONResponse({'detail':'Requisição sem proteção de origem.'},403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    if request.url.path.startswith('/api/'): response.headers['Cache-Control']='no-store'
    return response

def signed(value): return hmac.new(SECRET.encode(),value.encode(),hashlib.sha256).hexdigest()

def auth(request:Request):
    if LOCAL:
        if not request.client or request.client.host not in ('127.0.0.1','::1','testclient'):
            raise HTTPException(403,'Modo local só aceita conexão local. Configure autenticação para publicar.')
        return
    token=request.cookies.get('vf_session','')
    try:
        value,signature=token.rsplit('.',1); expiry=int(value.split('.')[0])
        if expiry<time.time() or not hmac.compare_digest(signature,signed(value)): raise ValueError()
    except (ValueError,IndexError): raise HTTPException(401,'Entre com a senha do seu estúdio.')

class Login(BaseModel): password:str=Field(min_length=1,max_length=512)

@app.post('/api/login')
def login(body:Login,request:Request,response:Response):
    ip=request.client.host if request.client else 'unknown'; now=time.time()
    attempts=[t for t in ATTEMPTS.get(ip,[]) if now-t<300]
    if len(attempts)>=8: raise HTTPException(429,'Muitas tentativas. Tente novamente em alguns minutos.')
    if not PASSWORD or not hmac.compare_digest(hashlib.sha256(body.password.encode()).digest(),hashlib.sha256(PASSWORD.encode()).digest()):
        ATTEMPTS[ip]=attempts+[now]; raise HTTPException(401,'Senha incorreta.')
    ATTEMPTS.pop(ip,None)
    value=f'{int(now)+86400}.{secrets.token_hex(12)}'
    response.set_cookie('vf_session',value+'.'+signed(value),httponly=True,secure=not LOCAL,samesite='strict',max_age=86400,path='/')
    return {'ok':True}

@app.post('/api/logout')
def logout(response:Response):
    response.delete_cookie('vf_session',path='/'); return {'ok':True}

@app.get('/health')
def public_health(): return {'ok':True,'service':'video-factory'}

@app.get('/api/status',dependencies=[Depends(auth)])
def status():
    ffmpeg=bool(shutil.which(media.FFMPEG) and shutil.which(media.FFPROBE))
    return {'ok':True,'version':'0.2.0','local':LOCAL,'render':ffmpeg,'auto_captions':media.asr_available(),
            'lip_sync':False,'face_tracking':False,'background_removal_without_green':False,
            'disk_free_mb':shutil.disk_usage(db.ROOT).free//1024**2,'max_upload_mb':db.MAX_UPLOAD//1024**2}

class Project(BaseModel): name:str=Field(min_length=1,max_length=80)

@app.get('/api/projects',dependencies=[Depends(auth)])
def projects(): return db.records('project')

@app.post('/api/projects',dependencies=[Depends(auth)])
def create_project(body:Project):
    if len(db.records('project'))>=100: raise ValueError('Limite de 100 projetos. Exclua projetos antigos.')
    return db.put('project',{'id':db.ident(),'name':body.name,'created':time.time(),'settings':db.Settings().model_dump()})

@app.get('/api/projects/{pid}',dependencies=[Depends(auth)])
def project(pid:str):
    result=db.get('project',pid)
    return {**result,'assets':db.records('asset',pid),'jobs':[public_job(j) for j in reversed(db.records('job',pid))]}

@app.put('/api/projects/{pid}/settings',dependencies=[Depends(auth)])
def save_settings(pid:str,body:db.Settings): return db.patch('project',pid,settings=body.model_dump())

@app.delete('/api/projects/{pid}',dependencies=[Depends(auth)])
def delete_project(pid:str):
    db.get('project',pid)
    if any(j['status'] in ('queued','processing') for j in db.records('job')): raise HTTPException(409,'Aguarde ou cancele os lotes em andamento antes de excluir o projeto e limpar o cache.')
    for asset in db.records('asset',pid): db.asset_path(asset).unlink(missing_ok=True); db.remove('asset',asset['id'])
    for job in db.records('job',pid): shutil.rmtree(db.ROOT/'jobs'/job['id'],ignore_errors=True); db.remove('job',job['id'])
    db.remove('project',pid)
    shutil.rmtree(db.ROOT/'cache',ignore_errors=True); (db.ROOT/'cache').mkdir(exist_ok=True)
    return {'ok':True}

class UploadStart(BaseModel):
    name:str=Field(min_length=1,max_length=220)
    size:int=Field(gt=0)
    kind:Literal['hook','body','cta','support','music']

@app.post('/api/projects/{pid}/uploads',dependencies=[Depends(auth)])
def upload_start(pid:str,body:UploadStart):
    db.get('project',pid)
    if body.size>db.MAX_UPLOAD: raise HTTPException(413,'Arquivo maior que o limite permitido.')
    extension=Path(body.name).suffix.lower()
    videos={'.mp4','.mov','.webm','.m4v'}; images={'.png','.jpg','.jpeg'}; sounds={'.mp3','.wav','.m4a','.ogg','.flac'}
    allowed=sounds if body.kind=='music' else videos|images if body.kind=='support' else videos
    if extension not in allowed: raise ValueError('Formato não aceito para este espaço.')
    with db.LOCK:
        if len(db.records('asset',pid))>=300: raise ValueError('Limite de 300 arquivos por projeto.')
        reserved=sum(a['size'] for a in db.records('asset'))
        if reserved+body.size>db.MAX_STORAGE or shutil.disk_usage(db.ROOT).free<body.size+100*1024**2:
            raise HTTPException(507,'Sem espaço suficiente. Exclua projetos antigos ou amplie o armazenamento.')
        item={'id':db.ident(),'project':pid,'name':body.name,'kind':body.kind,'ext':extension,'size':body.size,
              'received':0,'status':'uploading','image':extension in images,'cues':[],'trim_start':0,'trim_end':None}
        db.asset_path(item).touch(); db.put('asset',item)
    return item

@app.get('/api/uploads/{aid}',dependencies=[Depends(auth)])
def upload_info(aid:str):
    asset=db.get('asset',aid)
    if asset['status']=='uploading':
        asset['received']=db.asset_path(asset).stat().st_size
    return asset

@app.patch('/api/uploads/{aid}',dependencies=[Depends(auth)])
async def upload_chunk(aid:str,request:Request):
    try: offset=int(request.headers.get('upload-offset','-1'))
    except ValueError: raise HTTPException(400,'Offset inválido.')
    buffer=bytearray()
    async for chunk in request.stream():
        buffer.extend(chunk)
        if len(buffer)>2*1024**2: raise HTTPException(413,'O bloco deve ter no máximo 2 MB.')
    with db.LOCK:
        asset=db.get('asset',aid)
        if asset['status']!='uploading': raise HTTPException(409,'Upload já finalizado.')
        path=db.asset_path(asset); actual=path.stat().st_size
        if offset!=actual: raise HTTPException(409,f'Retome a partir do byte {actual}.')
        if actual+len(buffer)>asset['size']: raise HTTPException(413,'Bloco maior que o tamanho declarado.')
        with path.open('ab') as handle: handle.write(buffer); handle.flush(); os.fsync(handle.fileno())
        asset.update(received=actual+len(buffer)); db.put('asset',asset)
    return {'received':asset['received']}

@app.post('/api/uploads/{aid}/finish',dependencies=[Depends(auth)])
def upload_finish(aid:str):
    with db.LOCK:
        asset=db.get('asset',aid); path=db.asset_path(asset)
        if asset['status']=='ready': return asset
        if asset['status']=='processing': raise HTTPException(409,'Este arquivo já está sendo verificado.')
        if path.stat().st_size!=asset['size']: raise ValueError('O upload ainda não terminou.')
        db.patch('asset',aid,status='processing')
    try:
        with path.open('rb') as handle: magic=handle.read(32)
        known=(magic.startswith((b'\x89PNG',b'\xff\xd8\xff',b'\x1aE\xdf\xa3',b'RIFF',b'OggS',b'fLaC',b'ID3'))
               or magic[4:8] in (b'ftyp',b'moov',b'mdat',b'free',b'wide') or (len(magic)>1 and magic[0]==255 and magic[1]&224==224))
        if not known: raise ValueError('O conteúdo não corresponde a um arquivo de mídia aceito.')
        info=media.probe(path)
        if asset['kind']=='music' and not info['has_audio']: raise ValueError('Não encontrei áudio nesse arquivo.')
        if asset['kind']!='music' and not info['has_video']: raise ValueError('Não encontrei imagem nesse arquivo.')
        if not asset['image'] and (info['duration']<=.05 or info['duration']>600): raise ValueError('Use clipes entre 0,05 segundo e 10 minutos.')
        if max(info['width'],info['height'])>8192 or info['width']*info['height']>34000000: raise ValueError('Resolução acima do limite de segurança.')
        asset.update(info,status='ready',sha256=db.digest(path),received=asset['size'])
        return db.put('asset',asset)
    except Exception:
        db.patch('asset',aid,status='failed'); raise

@app.get('/api/assets/{aid}/media',dependencies=[Depends(auth)])
def asset_media(aid:str):
    asset=db.get('asset',aid)
    if asset['status']!='ready': raise HTTPException(409,'Arquivo ainda não está pronto.')
    return FileResponse(db.asset_path(asset))

class EditClip(BaseModel):
    trim_start:float=Field(default=0,ge=0,allow_inf_nan=False)
    trim_end:float|None=Field(default=None,gt=0,allow_inf_nan=False)
    cues:list[db.Cue]=Field(default_factory=list,max_length=2000)

@app.put('/api/assets/{aid}',dependencies=[Depends(auth)])
def edit_asset(aid:str,body:EditClip):
    asset=db.get('asset',aid)
    if asset['status']!='ready': raise ValueError('Aguarde o fim do upload.')
    end=body.trim_end or asset['duration']
    if body.trim_start>=end or end>asset['duration']+.05: raise ValueError('Confira os tempos de início e fim.')
    cues=[c.model_dump() for c in body.cues]
    if any(c['end']<=c['start'] or c['end']>asset['duration']+.05 for c in cues): raise ValueError('As legendas precisam estar dentro da duração do clipe.')
    return db.patch('asset',aid,trim_start=body.trim_start,trim_end=body.trim_end,cues=cues)

@app.delete('/api/assets/{aid}',dependencies=[Depends(auth)])
def delete_asset(aid:str):
    asset=db.get('asset',aid)
    if active(asset['project']): raise HTTPException(409,'Cancele o processamento antes de excluir arquivos.')
    db.asset_path(asset).unlink(missing_ok=True); db.remove('asset',aid); return {'ok':True}

def validated_plan(pid,body):
    db.get('project',pid); assets=[a for a in db.records('asset',pid) if a['status']=='ready']
    if body.settings.template!='solo' and not any(a['kind']=='support' for a in assets): raise ValueError('Adicione uma imagem ou vídeo de apoio para esse modelo.')
    if body.settings.captions=='auto' and not media.asr_available(): raise ValueError('Transcrição automática não configurada. Use SRT ou sem legendas.')
    result=db.plan(assets,body.count,body.seed,body.settings.max_seconds)
    if body.settings.captions=='import' and not any(a.get('cues') for a in assets if a['kind'] in ('hook','body','cta')):
        result['warnings'].append('Não há legendas importadas. O vídeo será exportado sem legendas de fala.')
    if any(not a['has_audio'] for a in assets if a['kind'] in ('hook','body','cta')):
        result['warnings'].append('Alguns clipes não têm áudio; seus trechos permanecerão sem fala.')
    if len([a for a in assets if a['kind']=='music'])>1: result['warnings'].append('Será usada a primeira trilha de música enviada.')
    return assets,result

@app.post('/api/projects/{pid}/plan',dependencies=[Depends(auth)])
def make_plan(pid:str,body:db.PlanRequest): return validated_plan(pid,body)[1]

class RenderRequest(db.PlanRequest): request_id:str=Field(pattern=r'^[a-zA-Z0-9-]{8,80}$')

def public_job(job): return {k:v for k,v in job.items() if k not in ('assets','request_id')}

@app.post('/api/projects/{pid}/jobs',dependencies=[Depends(auth)])
def create_job(pid:str,body:RenderRequest):
    with db.LOCK:
        existing=next((j for j in db.records('job',pid) if j.get('request_id')==body.request_id),None)
        if existing: return public_job(existing)
        if len([j for j in db.records('job') if j['status'] in ('queued','processing')])>=10: raise HTTPException(429,'A fila já contém 10 lotes. Aguarde os primeiros terminarem.')
        if not shutil.which(media.FFMPEG): raise HTTPException(503,'FFmpeg não está instalado no servidor.')
        assets,result=validated_plan(pid,body)
        job={'id':db.ident(),'project':pid,'request_id':body.request_id,'created':time.time(),'status':'queued','progress':0,
             'message':'Na fila','settings':body.settings.model_dump(),'assets':assets,**result,'outputs':[],'cancel':False}
        db.put('job',job); db.patch('project',pid,settings=body.settings.model_dump())
    WAKE.set(); return public_job(job)

@app.get('/api/jobs/{jid}',dependencies=[Depends(auth)])
def job_info(jid:str): return public_job(db.get('job',jid))

@app.post('/api/jobs/{jid}/cancel',dependencies=[Depends(auth)])
def cancel_job(jid:str):
    with db.LOCK:
        job=db.get('job',jid)
        if job['status'] in ('queued','processing'):
            job.update(cancel=True,status='cancelled' if job['status']=='queued' else job['status']); db.put('job',job)
    return public_job(job)

@app.post('/api/jobs/{jid}/retry',dependencies=[Depends(auth)])
def retry_job(jid:str):
    with db.LOCK:
        job=db.get('job',jid)
        if job['status'] not in ('failed','cancelled'): raise HTTPException(409,'Este lote não precisa ser retomado.')
        db.patch('job',jid,cancel=False,status='queued',error=None)
    WAKE.set(); return public_job(db.get('job',jid))

@app.get('/api/jobs/{jid}/files/{filename}',dependencies=[Depends(auth)])
def download(jid:str,filename:str):
    job=db.get('job',jid)
    allowed=[o['file'] for o in job['outputs']]+(['videos.zip'] if job['status']=='completed' else [])
    if filename not in allowed: raise HTTPException(404,'Arquivo não disponível.')
    path=db.ROOT/'jobs'/db.valid_id(jid)/filename
    return FileResponse(path,filename=filename,content_disposition_type='attachment' if filename.endswith('.zip') else 'inline')

app.mount('/',StaticFiles(directory=STUDIO,html=True),name='studio')
