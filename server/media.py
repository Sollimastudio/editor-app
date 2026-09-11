from __future__ import annotations
import hashlib, importlib.util, json, math, os, re, shutil, subprocess, tempfile, time
from pathlib import Path
from .core import ROOT, Settings, asset_path, digest

class Cancelled(Exception): pass

FFMPEG = os.getenv('FFMPEG_BIN','ffmpeg')
FFPROBE = os.getenv('FFPROBE_BIN','ffprobe')
THREADS = max(1,min(4,int(os.getenv('RENDER_THREADS','2'))))

# No shell interpolation; input protocols are limited to local files.
def run(args: list[str], cancelled=lambda:False, timeout=1800) -> str:
    with tempfile.TemporaryFile(mode='w+b') as log:
        proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
        started=time.monotonic()
        try:
            while proc.poll() is None:
                if cancelled(): raise Cancelled('Processamento cancelado.')
                if time.monotonic()-started>timeout: raise RuntimeError('O processamento ultrapassou o limite de segurança.')
                time.sleep(.08)
        except BaseException:
            proc.terminate()
            try: proc.wait(timeout=3)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait()
            raise
        log.seek(0); output=log.read().decode('utf8',errors='replace')
    if proc.returncode:
        raise RuntimeError('FFmpeg não conseguiu processar a mídia. ' + output[-1400:])
    return output

def base():
    return [FFMPEG,'-hide_banner','-nostdin','-y','-threads',str(THREADS),'-filter_complex_threads','1','-filter_threads','1']

def source(path: Path, image=False, loop=False):
    extra=['-loop','1','-framerate','30'] if image else (['-stream_loop','-1'] if loop else [])
    return extra+['-protocol_whitelist','file,pipe','-i',str(path)]

def probe(path: Path):
    text=run([FFPROBE,'-v','error','-protocol_whitelist','file,pipe','-show_streams','-show_format','-of','json',str(path)],timeout=30)
    data=json.loads(text); streams=data.get('streams',[])
    video=next((x for x in streams if x['codec_type']=='video'),None)
    audio=next((x for x in streams if x['codec_type']=='audio'),None)
    duration=float(data.get('format',{}).get('duration') or (video or audio or {}).get('duration') or 0)
    if not math.isfinite(duration): raise ValueError('Duração inválida.')
    return {'width':int((video or {}).get('width',0)), 'height':int((video or {}).get('height',0)),
            'duration':duration,'has_audio':audio is not None,'has_video':video is not None,
            'video_codec':(video or {}).get('codec_name'),'audio_codec':(audio or {}).get('codec_name')}

def encode():
    return ['-c:v','libx264','-preset','veryfast','-crf','21','-pix_fmt','yuv420p','-r','30',
            '-threads',str(THREADS),'-c:a','aac','-b:a','160k','-ar','48000','-ac','2','-movflags','+faststart']

def speech_ranges(path:Path, start:float, end:float, cancelled):
    length=end-start
    log=run(base()+['-ss',str(start)]+source(path)+['-t',str(length),'-vn','-af','silencedetect=noise=-38dB:d=0.8','-f','null','-'],cancelled)
    events=re.findall(r'silence_(start|end): ([0-9.]+)',log)
    silent=[]; current=None
    for typ,num in events:
        value=min(length,max(0,float(num)))
        if typ=='start': current=value
        elif current is not None: silent.append((current,value)); current=None
    if current is not None: silent.append((current,length))
    keep=[]; cursor=0
    for a,b in silent:
        cut_start=max(0,a+.18) if a>.05 else 0
        cut_end=min(length,b-.18) if b<length-.05 else length
        if cut_end<=cut_start: continue
        if cut_start>cursor+.06: keep.append((cursor,cut_start))
        cursor=max(cursor,cut_end)
    if cursor<length-.06: keep.append((cursor,length))
    # Entirely silent recordings stay intact; never turn a clip into an empty file.
    if not keep or len(keep)>30: keep=[(0,length)]
    return [(a+start,b+start) for a,b in keep]

def remap_cues(cues, ranges):
    output=[]; offset=0
    for a,b in ranges:
        for cue in cues:
            left=max(a,cue['start']); right=min(b,cue['end'])
            if right>left:
                output.append({'start':offset+left-a,'end':offset+right-a,'text':cue['text']})
        offset+=b-a
    return output

def asr_available():
    return bool(os.getenv('WHISPER_MODEL')) and importlib.util.find_spec('faster_whisper') is not None

_MODEL=None

def transcribe(path:Path):
    global _MODEL
    if not asr_available(): raise ValueError('Transcrição automática não configurada. Importe um SRT ou ative o modelo no servidor.')
    from faster_whisper import WhisperModel
    if _MODEL is None:
        _MODEL=WhisperModel(os.environ['WHISPER_MODEL'],device='cpu',compute_type='int8',cpu_threads=THREADS)
    segments,_ = _MODEL.transcribe(str(path),language='pt',word_timestamps=True,vad_filter=True,beam_size=3)
    cues=[]
    for segment in segments:
        words=list(segment.words or [])
        for i in range(0,len(words),6):
            group=words[i:i+6]
            cues.append({'start':group[0].start,'end':group[-1].end,'text':''.join(w.word for w in group).strip()})
    return cues

def prepare(asset:dict, settings:Settings, cancelled):
    fingerprint=json.dumps({'v':5,'template':settings.template,'resolution':settings.resolution,'fit':settings.fit,'chroma_color':settings.chroma_color,'hash':asset['sha256'],'start':asset.get('trim_start',0),'end':asset.get('trim_end'),
                            'silence':settings.trim_silence,'normal':settings.normalize_audio,'captions':settings.captions,
                            'cues':asset.get('cues',[]),'asr':os.getenv('WHISPER_MODEL','')},sort_keys=True)
    key=hashlib.sha256(fingerprint.encode()).hexdigest()
    target=ROOT/'cache'/f'{key}.mp4'; sidecar=target.with_suffix('.json')
    if target.exists() and sidecar.exists(): return target,json.loads(sidecar.read_text())
    start=asset.get('trim_start',0); end=asset.get('trim_end') or asset['duration']
    path=asset_path(asset)
    ranges=speech_ranges(path,start,end,cancelled) if settings.trim_silence and asset['has_audio'] else [(start,end)]
    n=len(ranges); total=sum(b-a for a,b in ranges)
    pw,ph=primary_size(settings)
    framefit=fit(pw,ph,settings.fit)
    if settings.template=='chroma': framefit=framefit.replace('0x18151c',settings.chroma_color.replace('#','0x'))
    filters=[]; args=base()+source(path)
    if not asset['has_audio']:
        args+=['-f','lavfi','-i','anullsrc=r=48000:cl=stereo']
    aud='0:a' if asset['has_audio'] else '1:a'
    if n>1:
        filters += [f'[0:v]split={n}'+''.join(f'[vs{i}]' for i in range(n)),f'[{aud}]asplit={n}'+''.join(f'[as{i}]' for i in range(n))]
    for i,(a,b) in enumerate(ranges):
        vi=f'vs{i}' if n>1 else '0:v'; ai=f'as{i}' if n>1 else aud
        filters += [f'[{vi}]trim=start={a}:end={b},setpts=PTS-STARTPTS,fps=30,{framefit}[v{i}]',
                    f'[{ai}]atrim=start={a}:end={b},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo[a{i}]']
    filters += [''.join(f'[v{i}][a{i}]' for i in range(n))+f'concat=n={n}:v=1:a=1[v][rawa]']
    normal=settings.normalize_audio and asset['has_audio']
    if normal:
        levels=run(base()+source(path)+['-vn','-af','volumedetect','-f','null','-'],cancelled)
        peak=re.search(r'max_volume: (-?[0-9.]+) dB',levels)
        normal=bool(peak and float(peak.group(1))>-80)
    audio='loudnorm=I=-16:TP=-1.5:LRA=11' if normal else 'anull'
    filters += [f'[rawa]{audio},aresample=48000[a]']
    tmp=target.with_suffix('.partial.mp4')
    try:
        run(args+['-filter_complex',';'.join(filters),'-map','[v]','-map','[a]','-t',str(total)]+encode()+[str(tmp)],cancelled)
        info=probe(tmp)
        cues=remap_cues(asset.get('cues',[]),ranges)
        if settings.captions=='auto': cues=transcribe(tmp)
        info.update(cues=cues,ranges=ranges,source_sha=asset['sha256'])
        tmp.replace(target); sidecar.write_text(json.dumps(info,ensure_ascii=False))
    finally:
        tmp.unlink(missing_ok=True)
    return target,info

def primary_size(settings: Settings):
    w=int(settings.resolution); h=w*16//9
    if h%2: h+=1
    if settings.template=='stack': return w,h//2//2*2
    if settings.template=='side': return w//2//2*2,h
    if settings.template=='pip': return round(w*.38)//2*2,round(h*.33)//2*2
    if settings.template=='card': return w//2//2*2,round(h*.28)//2*2
    return w,h

def fit(w:int,h:int,mode='contain'):
    if mode=='cover': return f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1'
    return f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=0x18151c,setsar=1'

def stamp(t):
    cent=max(0,round(t*100)); secs,c=divmod(cent,100); minutes,s=divmod(secs,60); h,m=divmod(minutes,60)
    return f'{h}:{m:02d}:{s:02d}.{c:02d}'

def safe_ass(text):
    return text.replace('\\','／').replace('{','(').replace('}',')').replace('\r','').replace('\n','\\N')

def subtitle_file(path:Path,settings:Settings,cues:list,seconds:float,w:int,h:int):
    color='&H00'+settings.caption_color[5:7]+settings.caption_color[3:5]+settings.caption_color[1:3]
    font=max(18,round(w*.052)); margin=round(h*.12)
    header=f'''[Script Info]\nScriptType: v4.00+\nPlayResX: {w}\nPlayResY: {h}\nWrapStyle: 0\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Caption,Liberation Sans,{font},{color},&H000000FF,&H00202020,&H90000000,-1,0,0,0,100,100,0,0,1,2.5,1,2,{round(w*.08)},{round(w*.08)},{margin},1\nStyle: Title,Liberation Sans,{round(font*1.12)},&H00FFFFFF,&H000000FF,&H00322025,&H90000000,-1,0,0,0,100,100,0,0,3,8,0,8,{round(w*.08)},{round(w*.08)},{round(h*.07)},1\nStyle: Brand,Liberation Sans,{round(font*.48)},&H00FFFFFF,&H000000FF,&H00322025,&H90000000,0,0,0,0,100,100,0,0,1,1,0,9,25,25,25,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'''
    def line(a,b,style,text):
        return f'Dialogue: 0,{stamp(a)},{stamp(b)},{style},,0,0,0,,{safe_ass(text)}\n'
    if settings.captions!='off':
        for c in cues:
            if c['start']<seconds: header+=line(c['start'],min(seconds,c['end']),'Caption',c['text'])
    if settings.title: header+=line(0,min(3,seconds),'Title',settings.title)
    if settings.signature: header+=line(0,seconds,'Brand',settings.signature)
    path.write_text(header,encoding='utf8')

def compose(parts:list[tuple],support:dict|None,music:dict|None,settings:Settings,destination:Path,cancelled):
    destination.parent.mkdir(exist_ok=True,parents=True)
    work=destination.parent/f'tmp-{destination.stem}'; work.mkdir(exist_ok=True)
    concat=work/'inputs.txt'
    # Paths are generated by the server; not controlled by input filenames.
    concat.write_text('\n'.join(f"file '{p.as_posix()}'" for p,_ in parts))
    joined=work/'joined.mp4'
    try:
        run(base()+['-f','concat','-safe','0','-protocol_whitelist','file,pipe','-i',str(concat),'-c','copy',str(joined)],cancelled)
        seconds=probe(joined)['duration']; w=int(settings.resolution); h=w*16//9
        if h%2: h+=1
        cues=[]; offset=0
        for _,info in parts:
            cues += [{'start':c['start']+offset,'end':c['end']+offset,'text':c['text']} for c in info['cues']]
            offset+=info['duration']
        subtitle_file(work/'captions.ass',settings,cues,seconds,w,h)
        args=base()+source(joined); filters=[]; next_input=1
        if settings.template!='solo':
            if not support: raise ValueError('Este template precisa de uma imagem ou vídeo de apoio.')
            args+=source(asset_path(support),image=support['image'],loop=not support['image']); next_input+=1
        template=settings.template
        if template=='solo': filters+=[f'[0:v]{fit(w,h,settings.fit)}[layout]']
        elif template=='stack':
            hh=h//2; hh-=hh%2
            filters += [f'[0:v]{fit(w,hh,settings.fit)}[first]',f'[1:v]{fit(w,h-hh)}[second]', '[first][second]vstack=inputs=2[layout]']
        elif template=='side':
            hw=w//2; hw-=hw%2
            filters += [f'[0:v]{fit(hw,h,settings.fit)}[first]',f'[1:v]{fit(w-hw,h)}[second]','[first][second]hstack=inputs=2[layout]']
        elif template in ('pip','card'):
            pw=round(w*.38)//2*2; ph=round(h*.33)//2*2
            filters += [f'[1:v]{fit(w,h)}[background]',f'[0:v]{fit(pw,ph,settings.fit)},drawbox=x=0:y=0:w=iw:h=ih:color=white:t=3[foreground]',f'[background][foreground]overlay=x={w-pw-round(w*.05)}:y={round(h*.51)}:shortest=1[layout]']
            if template=='card':
                filters=[f'[1:v]{fit(w,round(h*.64)//2*2)},pad={w}:{h}:0:0:color=0xf5efe9[background]',f'[0:v]{fit(w//2//2*2,round(h*.28)//2*2,settings.fit)}[foreground]',f'[background][foreground]overlay=x=(W-w)/2:y={round(h*.65)}:shortest=1[layout]']
        elif template=='chroma':
            chroma=settings.chroma_color.replace('#','0x')
            filters += [f'[1:v]{fit(w,h)}[background]',f'[0:v]format=rgba,colorkey={chroma}:{settings.chroma_similarity}:0.08,scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=0x00000000[foreground]', '[background][foreground]overlay=shortest=1[layout]']
        if settings.gentle_zoom:
            filters += [f"[layout]zoompan=z='min(1+on*0.00004,1.04)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={w}x{h}:fps=30[moving]"]
            layer='moving'
        else: layer='layout'
        # ASS file path is an internal UUID directory and never user text.
        filters += [f"[{layer}]ass='{(work/'captions.ass').as_posix()}',fps=30,format=yuv420p[outv]"]
        if music:
            args+=source(asset_path(music),loop=True)
            filters += ['[0:a]asplit=2[voice][sidechain]',f'[{next_input}:a]volume={settings.music_volume},aresample=48000[bgm]',
                        '[bgm][sidechain]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=300[ducked]',
                        '[voice][ducked]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[outa]']
        else: filters+=['[0:a]anull[outa]']
        tmp=destination.with_suffix('.partial.mp4')
        run(args+['-filter_complex',';'.join(filters),'-map','[outv]','-map','[outa]','-t',str(seconds)]+encode()+[str(tmp)],cancelled)
        check=probe(tmp)
        if check['width']!=w or check['height']!=h or check['video_codec']!='h264' or not check['has_audio']:
            raise RuntimeError('O arquivo não passou na verificação de saída.')
        tmp.replace(destination)
        return check
    finally:
        destination.with_suffix('.partial.mp4').unlink(missing_ok=True)
        shutil.rmtree(work,ignore_errors=True)
