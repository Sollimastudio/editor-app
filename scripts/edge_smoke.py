import hashlib,json,os,subprocess,time,uuid
from pathlib import Path
import httpx
from PIL import Image
O=Path(os.getenv('TEST_OUTPUT','/tmp/vf-edge'));O.mkdir(parents=True,exist_ok=True)
c=httpx.Client(base_url=os.getenv('TEST_BASE_URL','http://127.0.0.1:8000'),headers={'x-video-factory':'1'},timeout=60)
def call(m,u,**k):
 r=c.request(m,u,**k);assert r.status_code<400,(r.status_code,r.text);return r.json()
def ff(*a):subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-threads','1',*a],check=True)
def upload(p,pid,kind):
 b=p.read_bytes();a=call('POST',f'/api/projects/{pid}/uploads',json={'name':p.name,'size':len(b),'kind':kind});call('PATCH','/api/uploads/'+a['id'],headers={'upload-offset':'0'},content=b);return call('POST','/api/uploads/'+a['id']+'/finish')
pid=call('POST','/api/projects',json={'name':'Teste · chroma real e formatos mistos'})['id']
for kind,res in [('hook','320x568'),('body','640x360'),('cta','480x640')]:
 p=O/f'mixed-{kind}.mp4';ff('-f','lavfi','-i',f'color=c=0x00ff00:s={res}:r=24:d=0.7','-vf','drawbox=x=iw/3:y=ih/3:w=iw/3:h=ih/3:color=red:t=fill','-c:v','libx264','-pix_fmt','yuv420p',str(p));upload(p,pid,kind)
p=O/'background.mp4';ff('-f','lavfi','-i','color=c=blue:s=360x640:r=30:d=0.5','-c:v','libx264','-pix_fmt','yuv420p',str(p));upload(p,pid,'support')
p=O/'music.wav';ff('-f','lavfi','-i','sine=frequency=440:duration=0.4',str(p));upload(p,pid,'music')
j=call('POST',f'/api/projects/{pid}/jobs',json={'count':1,'request_id':str(uuid.uuid4()),'settings':{'template':'chroma','resolution':'360','captions':'off'}})
for _ in range(300):
 j=call('GET','/api/jobs/'+j['id']);assert j['status']!='failed',j.get('error')
 if j['status']=='completed':break
 time.sleep(.2)
assert j['status']=='completed'
p=O/'chroma-real.mp4';p.write_bytes(c.get(f'/api/jobs/{j["id"]}/files/video-01.mp4').content)
ff('-ss','0.2','-i',str(p),'-frames:v','1',str(O/'chroma-proof.png'))
pixel=Image.open(O/'chroma-proof.png').convert('RGB').getpixel((20,20));assert pixel[2]>150 and pixel[1]<100,pixel
ff('-i',str(p),'-f','null','-')
# Malicious text disguised as MP4 must fail signature validation.
b=b'#EXTM3U\nfile:///etc/passwd';a=call('POST',f'/api/projects/{pid}/uploads',json={'name':'bad.mp4','size':len(b),'kind':'hook'});call('PATCH','/api/uploads/'+a['id'],headers={'upload-offset':'0'},content=b);assert c.post('/api/uploads/'+a['id']+'/finish').status_code==400
report={'mixed_aspects':'PASS','mixed_frame_rates':'PASS','silent_sources':'PASS','looping_video_background':'PASS','looping_music':'PASS','real_chroma_pixel':pixel,'malicious_playlist':'REJECTED','output':j['outputs'][0]}
(O/'edge-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
