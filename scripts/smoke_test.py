"""HTTP -> chunked upload -> actual FFmpeg -> MP4. No paid services."""
import hashlib,json,os,subprocess,time,uuid
from pathlib import Path
import httpx
from PIL import Image,ImageDraw
OUT=Path(os.getenv('TEST_OUTPUT','/tmp/vf-smoke'));OUT.mkdir(parents=True,exist_ok=True)
c=httpx.Client(base_url=os.getenv('TEST_BASE_URL','http://127.0.0.1:8000'),headers={'X-Video-Factory':'1'},timeout=60)
def call(m,u,**k):
 r=c.request(m,u,**k);assert r.status_code<400,(r.status_code,r.text);return r.json()
def ff(*a): subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-threads','1',*a],check=True)
def upload(pid,p,kind):
 b=p.read_bytes();a=call('POST',f'/api/projects/{pid}/uploads',json={'name':p.name,'size':len(b),'kind':kind});u='/api/uploads/'+a['id'];half=len(b)//2
 call('PATCH',u,headers={'upload-offset':'0'},content=b[:half]);assert c.patch(u,headers={'upload-offset':'0'},content=b'x').status_code==409
 call('PATCH',u,headers={'upload-offset':str(half)},content=b[half:]);a=call('POST',u+'/finish');assert a['sha256']==hashlib.sha256(b).hexdigest();return a

def wait(j):
 for _ in range(1200):
  j=call('GET','/api/jobs/'+j['id'])
  assert j['status']!='failed',j.get('error')
  if j['status']=='completed':return j
  time.sleep(.25)
 raise AssertionError('Timeout')
p=call('POST','/api/projects',json={'name':'Teste real · lote e templates'});pid=p['id'];assets=[]
for kind,n in [('hook',5),('body',3),('cta',5)]:
 for i in range(n):
  p=OUT/f'{kind}-{i}.mp4';color={'hook':'9b4256','body':'456250','cta':'374868'}[kind]
  ff('-f','lavfi','-i',f'color=c=0x{color}:s=320x568:r=30:d=0.7','-f','lavfi','-i',f'sine=frequency={400+70*i}:sample_rate=48000:duration=0.7','-vf',f"drawtext=text='{kind} {i}':fontsize=35:fontcolor=white:x=(w-tw)/2:y=(h-th)/2",'-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(p));assets.append(upload(pid,p,kind))
print('13 uploaded clips PASS',flush=True)
im=Image.new('RGB',(600,800),'#ecdfc7');d=ImageDraw.Draw(im);d.rectangle([50,60,550,740],outline='#784155',width=12);d.text((100,300),'VIDEO FACTORY - TESTE',fill='#48233b');p=OUT/'support.png';im.save(p);upload(pid,p,'support')
call('PUT','/api/assets/'+assets[0]['id'],json={'trim_start':.1,'trim_end':.65,'cues':[{'start':.1,'end':.6,'text':'Legenda de teste'}]})
req={'count':15,'seed':12345,'settings':{'resolution':'360','template':'solo','title':'Teste de exportação','signature':'Sol Studio'}}
plan=call('POST',f'/api/projects/{pid}/plan',json=req);assert len(plan['variations'])==15 and len({tuple(v) for v in plan['variations']})==15 and plan['possible']==75
job=wait(call('POST',f'/api/projects/{pid}/jobs',json={**req,'request_id':str(uuid.uuid4())}));assert len(job['outputs'])==15
(OUT/'15-videos.zip').write_bytes(c.get(f'/api/jobs/{job["id"]}/files/videos.zip').content)
print('15 MP4s, 75 possible, unique combinations PASS',flush=True)
report={'project':pid,'batch_id':job['id'],'outputs':15,'templates':[]}
for i,t in enumerate(['solo','stack','side','pip','chroma','card']):
 req={'count':1,'seed':44+i,'settings':{'resolution':'1080' if t=='solo' else '360','template':t,'title':'Template '+t,'gentle_zoom':t=='solo','trim_silence':True},'request_id':str(uuid.uuid4())}
 j=call('POST',f'/api/projects/{pid}/jobs',json=req);again=call('POST',f'/api/projects/{pid}/jobs',json=req);assert j['id']==again['id'];j=wait(j);o=j['outputs'][0]
 (OUT/f'template-{t}.mp4').write_bytes(c.get(f'/api/jobs/{j["id"]}/files/{o["file"]}').content);report['templates'].append({'template':t,'output':o});print(t,'PASS',o['width'],o['height'],flush=True)
assert c.get('/api/assets/invalid/media').status_code==400
assert c.post(f'/api/projects/{pid}/jobs',json={'count':1,'settings':{'captions':'auto'},'request_id':str(uuid.uuid4())}).status_code==400
assert c.post('/api/projects',json={'name':'blocked'},headers={'X-Video-Factory':'0'}).status_code==403
(OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print('ALL PASSED',flush=True)
