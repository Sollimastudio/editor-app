import os,math
os.environ.setdefault('APP_ENV','local')
import pytest
from pydantic import ValidationError
from server.core import plan,Settings,Cue,valid_id
from server.media import remap_cues,safe_ass,primary_size

def items(h=5,b=3,c=5):
 return [{'id':f'{kind}{n}','kind':kind,'status':'ready','duration':5} for kind,count in [('hook',h),('body',b),('cta',c)] for n in range(count)]

def test_75_possible_15_unique_and_deterministic():
 a=items();p=plan(a,15,5,180)
 assert p['possible']==75 and len(p['variations'])==15
 assert len({tuple(v) for v in p['variations']})==15
 assert p==plan(a,15,5,180)
 assert p['variations']!=plan(a,15,6,180)['variations']

def test_balanced():
 p=plan(items(),15,12345,180)
 for group in p['usage']:
  assert max(group.values())-min(group.values())<=1

def test_missing_bucket():
 with pytest.raises(ValueError): plan(items(c=0),15,1,180)

def test_no_duplicate_when_request_exceeds_available():
 p=plan(items(1,1,1),15,1,180)
 assert len(p['variations'])==1 and p['warnings']

def test_duration_limit():
 with pytest.raises(ValueError): plan(items(),15,1,3)

def test_invalid_settings_rejected():
 for value in ({'template':'oops'},{'resolution':'4k'},{'chroma_color':"#fff;cat /etc/passwd"},{'lip_sync':True},{'max_seconds':100000}):
  with pytest.raises(ValidationError): Settings(**value)

def test_cue_rejects_nan():
 with pytest.raises(ValidationError): Cue(start=math.nan,end=1,text='bad')

def test_cut_remaps_captions():
 c=remap_cues([{'start':3,'end':5,'text':'hello'}],[(1,2),(3,6)])
 assert c==[{'start':1,'end':3,'text':'hello'}]

def test_ass_injection_is_not_executable_markup():
 assert '{' not in safe_ass(r'{\pos(0,0)} hello')
 assert '\\pos' not in safe_ass(r'{\pos(0,0)} hello')

def test_templates_use_even_dimensions():
 for t in ('solo','stack','side','pip','chroma','card'):
  for resolution in ('360','720','1080'):
   w,h=primary_size(Settings(template=t,resolution=resolution));assert w%2==h%2==0 and min(w,h)>0

def test_path_validation():
 for path in ['../../etc/passwd','x',"';rm -rf /",'00000000-0000-0000-0000-00000000000z']:
  with pytest.raises(ValueError): valid_id(path)
