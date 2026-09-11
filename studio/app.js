'use strict';
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state={project:null,assets:[],jobs:[],template:'solo',seed:Math.floor(Math.random()*1e8),status:null,busy:false,edit:null};
const templates=[
 {id:'solo',name:'Fala direta',desc:'Você em destaque, sem distração.',badge:'ESSENCIAL'},
 {id:'stack',name:'Tela repartida',desc:'Você em cima. Apoio embaixo.',badge:'DOIS ESPAÇOS'},
 {id:'side',name:'Lado a lado',desc:'Duas imagens, na mesma conversa.',badge:'DOIS ESPAÇOS'},
 {id:'pip',name:'Reação',desc:'Apoio grande. Você em uma janela.',badge:'SOBREPOSIÇÃO'},
 {id:'chroma',name:'Fundo verde',desc:'Troque o verde por imagem ou vídeo.',badge:'CHROMA KEY'},
 {id:'card',name:'Print + você',desc:'Documento em cima. Sua fala embaixo.',badge:'EXPLICAÇÃO'}
];
const labels={hook:['ABERTURAS','A primeira frase de cada vídeo.'],body:['CONTEÚDOS','A mensagem principal.'],cta:['ENCERRAMENTOS','Como você fecha a conversa.']};
function toast(text,error=false){$('toast').textContent=text;$('toast').className='toast'+(error?' toast-error':'');clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').classList.add('hidden'),error?10000:4500);}
async function api(path,options={}){
 const res=await fetch('/api'+path,{...options,headers:{'X-Video-Factory':'1',...(options.body&&typeof options.body==='string'?{'Content-Type':'application/json'}:{}),...options.headers},credentials:'same-origin'});
 if(res.status===401){$('login').classList.remove('hidden');$('shell').classList.add('hidden');throw new Error('Entre com a senha do estúdio.');}
 if(!res.ok){let err;try{err=await res.json();}catch{err={detail:'O servidor não respondeu como esperado.'};}throw new Error(typeof err.detail==='string'?err.detail:'Confira os campos preenchidos.');}
 return res.json();
}
const post=(path,body)=>api(path,{method:'POST',body:body?JSON.stringify(body):undefined});
function busy(value){state.busy=value;for(const id of ['generate','preview-render','remix','project-select','new-project'])$(id).disabled=value;}
function showResults(show){$('builder').classList.toggle('hidden',show);$('results').classList.toggle('hidden',!show);$('nav-create').classList.toggle('active',!show);$('nav-results').classList.toggle('active',show);}
function mediaURL(asset){return '/api/assets/'+encodeURIComponent(asset.id)+'/media';}
function size(n){return n>1024**2?(n/1024**2).toFixed(1)+' MB':Math.ceil(n/1024)+' KB';}
function duration(n){return Math.floor(n/60)+':'+String(Math.round(n%60)).padStart(2,'0');}
function assetHTML(asset){
 const ready=asset.status==='ready';
 const thumb=ready?(asset.image?`<img src="${mediaURL(asset)}" alt="" loading="lazy">`:asset.kind==='music'?'<span class="audio-symbol">♪</span>':`<video src="${mediaURL(asset)}" muted playsinline preload="metadata"></video>`):'<span class="audio-symbol">↑</span>';
 return `<article class="asset"><div class="asset-thumb">${thumb}</div><div class="asset-meta"><strong title="${esc(asset.name)}">${esc(asset.name)}</strong><small>${ready?(asset.image?'Imagem':duration(asset.duration))+' · '+size(asset.size):esc(asset.status==='uploading'?'Envio incompleto — selecione o arquivo novamente':asset.status==='processing'?'Verificando…':'Não foi possível validar')}</small><div class="asset-actions">${ready&&['hook','body','cta'].includes(asset.kind)?`<button data-edit="${asset.id}">Editar${asset.cues?.length?' · SRT':''}</button>`:''}<button data-delete="${asset.id}" aria-label="Remover ${esc(asset.name)}">Remover</button></div></div></article>`;
}
function renderAssets(){
 for(const kind of Object.keys(labels)){
  const items=state.assets.filter(a=>a.kind===kind);
  $('list-'+kind).innerHTML=items.map(assetHTML).join('');$('count-'+kind).textContent=items.filter(a=>a.status==='ready').length;
 }
 $('support-list').innerHTML=state.assets.filter(a=>a.kind==='support').map(assetHTML).join('');
 $('music-list').innerHTML=state.assets.filter(a=>a.kind==='music').map(assetHTML).join('');
 const possible=['hook','body','cta'].reduce((v,k)=>v*state.assets.filter(a=>a.kind===k&&a.status==='ready').length,1);
 $('possible').textContent=possible+' combinações';
 $('generation-note').textContent=possible?`Até ${possible} combinações com os clipes atuais. Máximo de 50 vídeos por lote.`:'Adicione uma abertura, um conteúdo e um encerramento para começar.';
 renderPreview();
}
function renderTemplates(){
 $('templates').innerHTML=templates.map(t=>`<button class="template ${state.template===t.id?'selected':''}" data-template="${t.id}" aria-pressed="${state.template===t.id}"><span class="template-demo ${t.id}"><i class="demo-a"></i><i class="demo-b"></i><span class="demo-line"></span></span><span class="template-badge">${t.badge}</span><strong>${t.name}</strong><small>${t.desc}</small></button>`).join('');
 $('preview-template-label').textContent=templates.find(t=>t.id===state.template).name;
 renderPreview();
}
function renderPreview(){
 const box=$('visual-preview');box.className='visual-preview '+state.template;
 const first=state.assets.find(a=>['hook','body'].includes(a.kind)&&a.status==='ready');
 const support=state.assets.find(a=>a.kind==='support'&&a.status==='ready');
 box.querySelector('.preview-speaker').innerHTML=first?`<video src="${mediaURL(first)}" muted playsinline preload="metadata"></video>`:'<span class="speaker-placeholder">Seu vídeo<small>aparece aqui</small></span>';
 box.querySelector('.preview-support').innerHTML=support?(support.image?`<img src="${mediaURL(support)}" alt="Mídia de apoio">`:`<video src="${mediaURL(support)}" muted playsinline preload="metadata"></video>`):'<span>IMAGEM / VÍDEO<br>DE APOIO</span>';
 box.querySelector('.preview-title').textContent=$('title').value;
 box.querySelector('.preview-signature').textContent=$('signature').value;
 box.querySelector('.preview-caption').classList.toggle('hidden',$('captions').value==='off');
}
function settings(){return {template:state.template,resolution:$('resolution').value,trim_silence:$('silence').checked,normalize_audio:$('normalize').checked,captions:$('captions').value,fit:$('fit').value,gentle_zoom:$('zoom').checked,title:$('title').value,signature:$('signature').value,caption_color:$('caption-color').value,chroma_color:$('chroma-color').value,chroma_similarity:Number($('chroma-similarity').value),music_volume:Number($('music-volume').value),max_seconds:Number($('max-seconds').value)};}
function applySettings(s){
 if(!s)return;state.template=s.template||'solo';
 const map={resolution:'resolution',captions:'captions',fit:'fit',title:'title',signature:'signature',caption_color:'caption-color',chroma_color:'chroma-color',chroma_similarity:'chroma-similarity',music_volume:'music-volume',max_seconds:'max-seconds'};
 for(const [key,id]of Object.entries(map))if(s[key]!==undefined)$(id).value=s[key];
 $('silence').checked=!!s.trim_silence;$('normalize').checked=!!s.normalize_audio;$('zoom').checked=!!s.gentle_zoom;
 if($('captions').value==='auto'&&!state.status?.auto_captions)$('captions').value='import';renderTemplates();
}
async function refreshProjects(preferred){
 const items=await api('/projects');
 if(!items.length){const p=await post('/projects',{name:'Meu primeiro projeto'});items.push(p);}
 $('project-select').innerHTML=items.map(p=>`<option value="${p.id}">${esc(p.name)}</option>`).join('');
 const chosen=items.find(p=>p.id===(preferred||localStorage.getItem('vf-project')))||items[0];
 $('project-select').value=chosen.id;await loadProject(chosen.id);
}
async function loadProject(id){
 const project=await api('/projects/'+id);state.project=project;state.assets=project.assets;state.jobs=project.jobs;
 localStorage.setItem('vf-project',id);applySettings(project.settings);renderAssets();renderJobs();
}
async function refreshAssets(){
 const id=state.project?.id;if(!id)return;
 const p=await api('/projects/'+id);if(id!==state.project?.id)return;state.assets=p.assets;state.jobs=p.jobs;renderAssets();renderJobs();
}
async function uploadFiles(kind,files){
 if(!files.length||state.busy)return;
 const project=state.project.id;busy(true);
 try{
  for(const file of files){
   const fingerprint=`vf-upload:${project}:${kind}:${file.name}:${file.size}:${file.lastModified}`;
   let asset;const stored=localStorage.getItem(fingerprint);
   if(stored){try{asset=await api('/uploads/'+stored);}catch{localStorage.removeItem(fingerprint);}}
   if(asset?.status==='ready'){toast(file.name+' já está no projeto.');continue;}
   if(asset?.status==='failed'){try{await api('/assets/'+asset.id,{method:'DELETE'});}catch{}asset=null;}
   if(!asset){asset=await post(`/projects/${project}/uploads`,{name:file.name,size:file.size,kind});localStorage.setItem(fingerprint,asset.id);}
   let offset=asset.received;
   while(offset<file.size){
    $('generation-note').textContent=`Enviando ${file.name} · ${Math.round(100*offset/file.size)}%. Mantenha esta página aberta até o envio terminar.`;
    const chunk=file.slice(offset,offset+2*1024**2);let sent=false;
    for(let attempt=0;attempt<3&&!sent;attempt++){
     try{const result=await api('/uploads/'+asset.id,{method:'PATCH',headers:{'Content-Type':'application/octet-stream','Upload-Offset':String(offset)},body:chunk});offset=result.received;sent=true;}
     catch(error){if(attempt===2)throw error;const check=await api('/uploads/'+asset.id);if(check.received>offset){offset=check.received;sent=true;}else await new Promise(r=>setTimeout(r,800));}
    }
   }
   $('generation-note').textContent='Conferindo '+file.name+'…';await post('/uploads/'+asset.id+'/finish');
   localStorage.removeItem(fingerprint);await refreshAssets();
  }
  toast('Arquivos recebidos. Agora é só escolher o visual.');
 }catch(error){toast(error.message+' Se o envio parou, selecione o mesmo arquivo para retomar.',true);await refreshAssets().catch(()=>{});}
 finally{busy(false);}
}
function renderJobs(){
 const complete=state.jobs.reduce((n,j)=>n+j.outputs.length,0);$('result-count').textContent=complete;
 if(!state.jobs.length){$('jobs-list').innerHTML='<div class="empty-state"><span>▷</span><h3>Seu primeiro vídeo começa no botão Gerar.</h3><p>Depois da exportação, os arquivos ficam organizados aqui.</p></div>';return;}
 const names={queued:'Na fila',processing:'Processando',completed:'Concluído',failed:'Precisa de atenção',cancelled:'Cancelado'};
 $('jobs-list').innerHTML=state.jobs.map(j=>`<article class="job"><div class="job-header"><div><span class="job-status ${j.status}">${names[j.status]}</span><h3>${j.variations.length} vídeo${j.variations.length>1?'s':''} · ${esc(templates.find(t=>t.id===j.settings.template)?.name)}</h3><small>${new Date(j.created*1000).toLocaleString('pt-BR')}</small></div><div>${j.status==='completed'?`<a class="primary" href="/api/jobs/${j.id}/files/videos.zip" download>↓ Baixar lote ZIP</a>`:['queued','processing'].includes(j.status)?`<button class="secondary" data-cancel="${j.id}">Cancelar lote</button>`:`<button class="secondary" data-retry="${j.id}">Retomar lote</button>`}</div></div><p class="muted">${esc(j.message)}</p>${['queued','processing'].includes(j.status)?`<progress max="100" value="${j.progress}"></progress>`:''}${j.error?`<details class="error"><summary>Ver detalhes da falha</summary><pre>${esc(j.error)}</pre></details>`:''}${j.warnings.length?`<div class="job-warnings">${j.warnings.map(w=>`<p>${esc(w)}</p>`).join('')}</div>`:''}<div class="output-grid">${j.outputs.map(o=>`<div class="output"><video src="/api/jobs/${j.id}/files/${o.file}" controls playsinline preload="none"></video><strong>${esc(o.file)}</strong><small>${o.width} × ${o.height} · ${duration(o.duration)}</small><a class="secondary full" href="/api/jobs/${j.id}/files/${o.file}" download="${o.file}">↓ Salvar MP4</a><details><summary>Clipes usados</summary><p>${o.clips.map(esc).join(' → ')}</p></details></div>`).join('')}</div></article>`).join('');
}
async function generate(preview=false){
 if(state.busy)return;busy(true);
 try{
  const s=settings();if(preview)s.resolution='360';
  const count=preview?1:Number($('count').value);const request={count,seed:state.seed,settings:s};
  const plan=await post('/projects/'+state.project.id+'/plan',request);
  const job=await post('/projects/'+state.project.id+'/jobs',{...request,request_id:crypto.randomUUID()});
  state.jobs.unshift(job);renderJobs();showResults(true);window.scrollTo({top:0,behavior:'smooth'});
  toast(preview?'Prévia leve de 1 vídeo enviada para exportação.':`${plan.variations.length} vídeos na fila. O servidor faz o restante.`);
 }catch(error){toast(error.message,true);}finally{busy(false);}
}
function srtTime(seconds){const ms=Math.round(seconds*1000),h=Math.floor(ms/3600000),m=Math.floor(ms/60000)%60,s=Math.floor(ms/1000)%60;return [h,m,s].map(n=>String(n).padStart(2,'0')).join(':')+','+String(ms%1000).padStart(3,'0');}
function cuesToSRT(cues){return cues.map((c,i)=>`${i+1}\n${srtTime(c.start)} --> ${srtTime(c.end)}\n${c.text}`).join('\n\n');}
function parseSRT(text){
 if(!text.trim())return[];
 const convert=t=>{const parts=t.replace(',','.').split(':').map(Number);return parts[0]*3600+parts[1]*60+parts[2];};
 return text.replace(/^\uFEFF/,'').replace(/\r/g,'').trim().split(/\n\s*\n/).map(block=>{
  const lines=block.split('\n');const idx=lines.findIndex(l=>l.includes('-->'));
  const m=(lines[idx]||'').match(/(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})/);
  if(!m||!lines.slice(idx+1).join('\n').trim())throw new Error('Confira o formato SRT: tempo inicial --> tempo final e texto abaixo.');
  return{start:convert(m[1]),end:convert(m[2]),text:lines.slice(idx+1).join('\n').trim()};
 });
}
function editClip(id){const a=state.assets.find(x=>x.id===id);state.edit=id;$('edit-name').textContent=a.name;$('edit-video').src=mediaURL(a);$('edit-start').value=a.trim_start||0;$('edit-end').value=(a.trim_end||a.duration).toFixed(2);$('edit-srt').value=cuesToSRT(a.cues||[]);$('edit-dialog').showModal();}
async function start(){
 try{state.status=await api('/status');$('login').classList.add('hidden');$('shell').classList.remove('hidden');$('connection-error').classList.add('hidden');
  $('server-label').textContent=state.status.render?'Servidor pronto para exportar':'FFmpeg não instalado';$('status-dot').classList.toggle('ready',state.status.render);
  $('logout').classList.toggle('hidden',state.status.local);
  const option=$('captions').querySelector('[value="auto"]');option.disabled=!state.status.auto_captions;option.textContent=state.status.auto_captions?'Automáticas · modelo configurado':'Automáticas · modelo não configurado';
  await refreshProjects();
 }catch(error){if(!$('shell').classList.contains('hidden')){$('connection-error').textContent='Não consegui conectar ao servidor. '+error.message;$('connection-error').classList.remove('hidden');}}
}
$('upload-grid').innerHTML=Object.entries(labels).map(([kind,[title,subtitle]],i)=>`<article class="upload-card"><div class="upload-card-heading"><span class="bucket-icon">0${i+1}</span><span class="count" id="count-${kind}">0</span></div><h3>${title}</h3><p>${subtitle}</p><label class="dropzone">＋<strong>Adicionar vídeos</strong><small>MP4, MOV ou WebM</small><input type="file" data-upload="${kind}" accept="video/mp4,video/quicktime,video/webm" multiple></label><div id="list-${kind}" class="asset-list"></div></article>`).join('');
renderTemplates();
document.addEventListener('change',event=>{const el=event.target;if(el.dataset.upload){uploadFiles(el.dataset.upload,Array.from(el.files));el.value='';}});
$('support-upload').onchange=e=>{uploadFiles('support',Array.from(e.target.files));e.target.value='';};
$('music-upload').onchange=e=>{uploadFiles('music',Array.from(e.target.files));e.target.value='';};
document.addEventListener('click',async event=>{
 const target=event.target.closest('button');if(!target)return;
 try{
  if(target.dataset.template){state.template=target.dataset.template;renderTemplates();}
  if(target.dataset.edit)editClip(target.dataset.edit);
  if(target.dataset.delete){if(!confirm('Remover este arquivo do projeto?'))return;await api('/assets/'+target.dataset.delete,{method:'DELETE'});await refreshAssets();}
  if(target.dataset.cancel){await post('/jobs/'+target.dataset.cancel+'/cancel');await refreshAssets();}
  if(target.dataset.retry){await post('/jobs/'+target.dataset.retry+'/retry');await refreshAssets();}
 }catch(error){toast(error.message,true);}
});
$('nav-create').onclick=()=>showResults(false);$('nav-results').onclick=()=>showResults(true);
$('new-project').onclick=()=>$('project-dialog').showModal();$('project-close').onclick=()=>$('project-dialog').close();
$('project-form').onsubmit=async e=>{e.preventDefault();try{const p=await post('/projects',{name:$('project-name').value});$('project-dialog').close();$('project-form').reset();await refreshProjects(p.id);showResults(false);}catch(error){toast(error.message,true);}};
$('project-select').onchange=e=>loadProject(e.target.value).catch(err=>toast(err.message,true));
$('delete-project').onclick=async()=>{if(!confirm('Excluir este projeto, seus arquivos e todos os vídeos exportados? Esta ação não pode ser desfeita.'))return;try{await api('/projects/'+state.project.id,{method:'DELETE'});await refreshProjects();}catch(error){toast(error.message,true);}};
$('generate').onclick=()=>generate();$('preview-render').onclick=()=>generate(true);
$('remix').onclick=()=>{state.seed=Math.floor(Math.random()*1e8);toast('Nova ordem selecionada. Clique em Gerar para criar o próximo lote.');};
$('save-preset').onclick=async()=>{try{await api('/projects/'+state.project.id+'/settings',{method:'PUT',body:JSON.stringify(settings())});localStorage.setItem('vf-style',JSON.stringify(settings()));toast('Seu estilo foi salvo neste projeto e neste navegador.');}catch(error){toast(error.message,true);}};
for(const id of ['title','signature','captions'])$(id).addEventListener('input',renderPreview);
$('refresh-results').onclick=()=>refreshAssets().catch(err=>toast(err.message,true));
$('edit-close').onclick=()=>{$('edit-video').pause();$('edit-dialog').close();};
$('edit-dialog').addEventListener('close',()=>$('edit-video').pause());
$('srt-upload').onchange=async e=>{const f=e.target.files[0];if(f){if(f.size>1024**2){toast('O SRT deve ter menos de 1 MB.',true);return;}$('edit-srt').value=await f.text();}e.target.value='';};
$('edit-form').onsubmit=async e=>{e.preventDefault();try{await api('/assets/'+state.edit,{method:'PUT',body:JSON.stringify({trim_start:Number($('edit-start').value),trim_end:Number($('edit-end').value),cues:parseSRT($('edit-srt').value)})});$('edit-dialog').close();await refreshAssets();toast('Clipe e legendas salvos. O original continua intacto.');}catch(error){toast(error.message,true);}};
$('login-form').onsubmit=async e=>{e.preventDefault();try{await post('/login',{password:$('password').value});$('password').value='';await start();}catch(error){$('login-error').textContent=error.message;}};
$('logout').onclick=async()=>{await post('/logout');$('login').classList.remove('hidden');$('shell').classList.add('hidden');};
setInterval(async()=>{if(!state.project||document.hidden||$('shell').classList.contains('hidden'))return;try{const p=await api('/projects/'+state.project.id);if(JSON.stringify(p.jobs)!==JSON.stringify(state.jobs)){state.jobs=p.jobs;renderJobs();}}catch{}},3000);
start();
