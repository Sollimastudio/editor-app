"""Offline visual/interaction check. Live navigation is blocked by the test browser policy."""
import json,re,os
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent
OUT=Path(os.getenv('TEST_OUTPUT','/tmp/vf-browser'));OUT.mkdir(parents=True,exist_ok=True)
html=(ROOT/'studio/index.html').read_text()
html=re.sub(r'<link[^>]+>','',html);html=re.sub(r'<script[^>]+>.*?</script>','',html)
css=(ROOT/'studio/style.css').read_text().replace("@import url('/fonts.css');",'')
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.getenv('CHROMIUM_BIN','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.set_content(html)
 page.add_style_tag(content=css)
 page.evaluate('''() => { const p={id:'11111111-1111-1111-1111-111111111111',name:'Meu primeiro projeto',settings:{template:'solo'},assets:[],jobs:[]};
 window.localStorage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};
 window.fetch=async u=>new Response(JSON.stringify(u==='/api/status'?{ok:true,render:true,local:true,auto_captions:false}:u==='/api/projects'?[p]:p),{status:200,headers:{'content-type':'application/json'}});
 }''')
 # about:blank's real localStorage is unavailable; use a minimal in-memory facade for visual tests.
 js=(ROOT/'studio/app.js').read_text().replace('localStorage','testStorage')
 page.evaluate('window.testStorage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}}')
 page.add_script_tag(content=js)
 page.wait_for_selector('#project-select option',state='attached',timeout=5000)
 page.screenshot(path=str(OUT/'editor-desktop.png'),full_page=True)
 page.locator('#nav-results').click();assert page.locator('#results').is_visible()
 page.locator('#nav-create').click();assert page.locator('#builder').is_visible()
 page.locator('[data-template="stack"]').click();assert 'stack' in page.locator('#visual-preview').get_attribute('class')
 page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(OUT/'editor-mobile.png'),full_page=True)
 assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
 assert not errors,errors
 print(json.dumps({'mode':'offline fixture, not deployed E2E','desktop':'PASS','mobile':'PASS','templates':page.locator('[data-template]').count(),'console_errors':errors,'navigation':'PASS'}))
 browser.close()
