#!/usr/bin/env python3
"""Render bilingual vertical shorts from stories/today.json."""
import asyncio
import json
import math
import subprocess
import tempfile
from pathlib import Path

import edge_tts
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'output'
STORY = ROOT / 'stories/today.json'
SIZE = (1080, 1920)
VOICES = {
    'zh': ('story_zh', 'zh-CN-YunyangNeural', '-12%', '-10Hz'),
    'en': ('story_en', 'en-US-AndrewNeural', '-15%', '-8Hz'),
}


def run(args):
    print('RUN:', ' '.join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), check=True)


def duration(path):
    return float(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(path)
    ], text=True).strip())


def font_path():
    options = [
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    ]
    return next((x for x in options if Path(x).exists()), options[-1])


def wrap(text, font, max_width):
    # CJK-aware character wrapping, preserves readable subtitles.
    lines, current = [], ''
    for ch in text:
        if ch == '\n':
            lines.append(current)
            current = ''
        elif ImageDraw.Draw(Image.new('RGB', (1, 1))).textbbox((0, 0), current + ch, font=font)[2] > max_width and current:
            lines.append(current)
            current = ch
        else:
            current += ch
    if current:
        lines.append(current)
    return lines


def make_placeholder(path, idx, count):
    # Visible atmospheric placeholder, so missing images don't silently produce black video.
    im = Image.new('RGB', SIZE, (10 + idx * 3, 16 + idx * 2, 24 + idx * 2))
    d = ImageDraw.Draw(im)
    for y in range(0, SIZE[1], 5):
        t = y / SIZE[1]
        shade = int(12 + 23 * (1 - abs(t - .48) * 2))
        d.line((0, y, SIZE[0], y), fill=(shade // 2, shade, shade + 8), width=5)
    d.rectangle((110, 280, 970, 1670), outline=(58, 74, 78), width=12)
    d.line((540, 280, 540, 1670), fill=(49, 65, 70), width=9)
    d.ellipse((470, 780, 610, 920), outline=(140, 30, 38), width=8)
    font = ImageFont.truetype(font_path(), 52)
    d.text((540, 1050), f'SCENE {idx + 1:02d} / {count:02d}', font=font, fill=(186, 200, 204), anchor='mm')
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path)


def subtitle_card(path, text, title):
    im = Image.new('RGBA', SIZE, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    title_font = ImageFont.truetype(font_path(), 45)
    font = ImageFont.truetype(font_path(), 55)
    lines = wrap(text, font, 890)
    # Avoid covering the whole frame with long text: only display a concise excerpt.
    lines = lines[:4]
    top = 1430 - len(lines) * 33
    d.rounded_rectangle((55, top - 48, 1025, top + 100 + 75 * len(lines)), radius=26, fill=(0, 0, 0, 185))
    d.text((540, top - 6), title[:38], font=title_font, fill=(220, 80, 86), anchor='mm')
    for i, line in enumerate(lines):
        d.text((540, top + 90 + i * 75), line, font=font, fill='white', anchor='mm', stroke_width=1, stroke_fill='black')
    im.save(path)


async def audio_for(data):
    for lang, (key, voice, rate, pitch) in VOICES.items():
        text = data[key]
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f'Missing story text: {key}')
        await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(str(OUTPUT / f'{lang}.mp3'))


def render(data, lang):
    audio = OUTPUT / f'{lang}.mp3'
    total = duration(audio)
    scenes = data['assets']['images']
    if not scenes:
        raise ValueError('assets.images must not be empty')
    # Scene durations track actual TTS duration, regardless of original estimates.
    per_scene = total / len(scenes)
    with tempfile.TemporaryDirectory() as tmp:
        temp = Path(tmp)
        clips = []
        for i, scene in enumerate(scenes):
            relative = Path(scene['file'])
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError(f'Unsafe image path: {relative}')
            image = ROOT / relative
            if not image.is_file():
                image = temp / f'placeholder_{i:02d}.png'
                print(f'WARNING: Missing {relative}; generating placeholder image', flush=True)
                make_placeholder(image, i, len(scenes))
            # Pre-scale to portrait canvas with cover crop.
            with Image.open(image) as src:
                src = src.convert('RGB')
                factor = max(SIZE[0] / src.width, SIZE[1] / src.height)
                new_size = (math.ceil(src.width * factor), math.ceil(src.height * factor))
                src = src.resize(new_size, Image.Resampling.LANCZOS)
                left = (src.width - SIZE[0]) // 2
                top = (src.height - SIZE[1]) // 2
                src.crop((left, top, left + SIZE[0], top + SIZE[1])).save(temp / f'base_{i:02d}.jpg', quality=91)
            clip = temp / f'clip_{i:02d}.mp4'
            frames = max(1, math.ceil(per_scene * 30))
            # Gentle slow zoom, no expensive external video model.
            vf = f'zoompan=z=min(zoom+0.00035\\,1.10):d={frames}:s=1080x1920:fps=30,format=yuv420p'
            run(['ffmpeg', '-y', '-loop', '1', '-i', temp / f'base_{i:02d}.jpg',
                 '-vf', vf, '-frames:v', str(frames), '-c:v', 'libx264',
                 '-preset', 'veryfast', '-crf', '25', '-an', clip])
            clips.append(clip)
        concat = temp / 'clips.txt'
        concat.write_text(''.join(f"file '{p.as_posix()}'\n" for p in clips), encoding='utf-8')
        title = data.get(f'title_{lang}', '')
        # Text is burned in as a title + story excerpt. Timed word-level subtitles can follow in V3.
        subtitle_card(temp / 'caption.png', data[f'story_{lang}'], title)
        video = OUTPUT / f'{lang}.mp4'
        run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', concat,
             '-i', audio, '-loop', '1', '-i', temp / 'caption.png',
             '-filter_complex', '[0:v][2:v]overlay=0:0:shortest=1[v]',
             '-map', '[v]', '-map', '1:a', '-t', f'{total:.3f}',
             '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '25',
             '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k',
             '-movflags', '+faststart', video])
        run(['ffmpeg', '-v', 'error', '-i', video, '-f', 'null', '-'])
        print(f'OK: {video.name} ({duration(video):.1f}s)', flush=True)


def main():
    data = json.loads(STORY.read_text(encoding='utf-8'))
    for key in ('date', 'title_zh', 'title_en', 'story_zh', 'story_en'):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f'Missing required field: {key}')
    if not isinstance(data.get('assets', {}).get('images'), list):
        raise ValueError('Missing assets.images list')
    OUTPUT.mkdir(exist_ok=True)
    asyncio.run(audio_for(data))
    for lang in VOICES:
        render(data, lang)


if __name__ == '__main__':
    main()
