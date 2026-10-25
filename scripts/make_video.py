#!/usr/bin/env python3
"""Generate bilingual test Shorts from stories/today.json."""
import asyncio
import json
import subprocess
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parents[1]
STORY = ROOT / "stories" / "today.json"
OUTPUT = ROOT / "output"
VOICES = {
    "zh": ("story_zh", "zh-CN-YunyangNeural", "-12%", "-10Hz"),
    "en": ("story_en", "en-US-AndrewNeural", "-15%", "-8Hz"),
}


def run(command):
    print("Running:", " ".join(map(str, command)), flush=True)
    subprocess.run(command, check=True)


async def generate_audio():
    with STORY.open(encoding="utf-8") as file:
        data = json.load(file)
    for required in ("date", "title_zh", "title_en", "story_zh", "story_en"):
        if not isinstance(data.get(required), str) or not data[required].strip():
            raise ValueError(f"Missing or empty string in JSON: {required}")
    OUTPUT.mkdir(exist_ok=True)
    for lang, (key, voice, rate, pitch) in VOICES.items():
        audio = OUTPUT / f"{lang}.mp3"
        await edge_tts.Communicate(data[key], voice, rate=rate, pitch=pitch).save(str(audio))
        if not audio.exists() or audio.stat().st_size == 0:
            raise RuntimeError(f"Audio was not generated: {audio}")


def render():
    for lang in VOICES:
        audio = OUTPUT / f"{lang}.mp3"
        video = OUTPUT / f"{lang}.mp4"
        run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1", str(audio)])
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1080x1920:r=30", "-i", str(audio), "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", str(video)])
        run(["ffmpeg", "-v", "error", "-i", str(video), "-f", "null", "-"])
        if not video.exists() or video.stat().st_size == 0:
            raise RuntimeError(f"Video was not generated: {video}")


if __name__ == "__main__":
    asyncio.run(generate_audio())
    render()
    print("SUCCESS: generated zh.mp3, en.mp3, zh.mp4, en.mp4")
