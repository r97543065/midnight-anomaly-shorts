#!/usr/bin/env python3
"""Bilingual FFmpeg shorts with per-scene motion, timed ASS captions and optional SFX."""
import asyncio, json, math, subprocess, tempfile, textwrap
from pathlib import Path
import edge_tts
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output'; SIZE=(1080,1920); FPS=30
VOICES={'zh':('zh-CN-YunyangNeural','-12%','-10Hz'),'en':('en-US-AndrewNeural','-15%','-8Hz')}
def run(*args):
    print('RUN', ' '.join(map(str,args)),flush=True)
    subprocess.run([str(x) for x in args],check=True)
def duration(p):
    return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(p)],text=True))
def font():
    for p in ['/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc','/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
        if Path(p).exists(): return p
    return '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
def placeholder(p,i):
    im=Image.new('RGB',SIZE,(12,22,29)); d=ImageDraw.Draw(im)
    d.rectangle((110,280,970,1660),outline=(55,80,85),width=12)
    d.line((540,280,540,1660),fill=(55,80,85),width=9)
    d.text((540,1080),f'SCENE {i+1:02}',font=ImageFont.truetype(font(),56),anchor='mm',fill='white');im.save(p)
def safe_file(value):
    p=Path(value)
    if p.is_absolute() or '..' in p.parts: raise ValueError(f'Unsafe path: {value}')
    return ROOT/p
def ass_time(s):
    h=int(s//3600);m=int(s//60)%60;sec=s%60
    return f'{h}:{m:02}:{sec:05.2f}'
def ass_escape(s):
    return str(s).replace('\\','\\\\').replace('{','(').replace('}',')').replace('\n',' ')
def captions(text,total,path):
    # Phrase-based estimated timing. For exact word timing, collect TTS boundary events later.
    import re
    phrases=[x.strip() for x in re.split(r'(?<=[。！？.!?，,；;])\s*',text) if x.strip()]
    if not phrases: phrases=[text]
    weights=[max(1,len(x)) for x in phrases]; cumulative=0; rows=[]
    for phrase,w in zip(phrases,weights):
        start=total*cumulative/sum(weights); cumulative+=w;end=total*cumulative/sum(weights)
        if end-start<0.15: continue
        if len(phrase)>24: phrase='\\N'.join(textwrap.wrap(phrase,24,break_long_words=True,break_on_hyphens=False))
        rows.append(f'Dialogue: 0,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,{ass_escape(phrase).replace(chr(92)+chr(92)+"N", chr(92)+"N")}')
    header='''[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Noto Sans CJK TC,64,&H00FFFFFF,&H00FFFFFF,&H00101010,&H90000000,1,0,0,0,100,100,0,0,1,4,2,2,70,70,260,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    path.write_text(header+'\n'.join(rows)+'\n',encoding='utf-8')
async def tts(data):
    for lang,(voice,rate,pitch) in VOICES.items():
        await edge_tts.Communicate(data['story_'+lang],voice,rate=rate,pitch=pitch).save(str(OUT/f'{lang}.mp3'))
def render(data,lang):
    audio=OUT/f'{lang}.mp3'; total=duration(audio); scenes=data['assets']['images'];n=len(scenes)
    with tempfile.TemporaryDirectory() as td:
        tmp=Path(td);clips=[]
        for i,scene in enumerate(scenes):
            image=safe_file(scene['file'])
            if not image.is_file():
                raise FileNotFoundError(f"Missing scene image: {scene['file']}")
            with Image.open(image) as src:
                src=src.convert('RGB'); factor=max(1080/src.width,1920/src.height)
                scaled=src.resize((math.ceil(src.width*factor),math.ceil(src.height*factor)),Image.Resampling.LANCZOS)
                x=(scaled.width-1080)//2;y=(scaled.height-1920)//2
                scaled.crop((x,y,x+1080,y+1920)).save(tmp/f'base{i}.jpg',quality=91)
            frames=max(1,math.ceil(total/n*FPS));effect=scene.get('effect',scene.get('camera','slow_zoom'))
            if effect=='static': vf='scale=1080:1920,format=yuv420p'
            elif effect=='pan_left': vf=f'zoompan=z=1.12:x=(iw-iw/zoom)*(1-on/{frames}):y=(ih-ih/zoom)/2:d={frames}:s=1080x1920:fps=30,format=yuv420p'
            elif effect=='pan_right': vf=f'zoompan=z=1.12:x=(iw-iw/zoom)*(on/{frames}):y=(ih-ih/zoom)/2:d={frames}:s=1080x1920:fps=30,format=yuv420p'
            else: vf=f'zoompan=z=min(zoom+0.00035\\,1.10):d={frames}:s=1080x1920:fps=30,format=yuv420p'
            effects=scene.get('effects',[])
            if 'film_grain' in effects: vf+=',noise=alls=7:allf=t'
            if 'flicker' in effects: vf+=',eq=brightness=0.035*sin(0.37*n)'
            clip=tmp/f'clip{i}.mp4'
            run('ffmpeg','-hide_banner','-loglevel','error','-y','-loop','1','-i',tmp/f'base{i}.jpg','-vf',vf,'-frames:v',frames,'-c:v','libx264','-preset','veryfast','-crf','26','-an',clip)
            clips.append(clip)
        manifest=tmp/'clips.txt';manifest.write_text(''.join(f"file '{p.as_posix()}'\n" for p in clips))
        subs=tmp/'subs.ass';captions(data['story_'+lang],total,subs)
        music=data.get('assets',{}).get('music');music=safe_file(music) if music else None
        cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',manifest,'-i',audio]
        mix='[1:a]volume=1[a]'
        if music and music.is_file():
            cmd+=['-stream_loop','-1','-i',music]
            mix='[1:a]volume=1[voice];[2:a]volume=0.12[bg];[voice][bg]amix=inputs=2:duration=first[a]'
        vf=f"[0:v]ass='{subs.as_posix()}'[v]"
        cmd+=['-filter_complex',vf+';'+mix,'-map','[v]','-map','[a]','-t',f'{total:.3f}','-c:v','libx264','-preset','veryfast','-crf','25','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-movflags','+faststart',OUT/f'{lang}.mp4']
        run(*cmd)
        print('OK',lang,duration(OUT/f'{lang}.mp4'),flush=True)
def main():
    data=json.loads((ROOT/'drafts/20261026-weather-radio/story.json').read_text(encoding='utf-8'))
    if not data['assets']['images']:raise ValueError('No images')
    OUT.mkdir(exist_ok=True)
    asyncio.run(tts(data))
    for lang in VOICES:render(data,lang)
if __name__=='__main__':main()
