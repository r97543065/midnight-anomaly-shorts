#!/usr/bin/env python3
"""Build two reproducible 9:16 horror shorts from stories/today.json."""
from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import tempfile
import textwrap
import time
from pathlib import Path

import edge_tts
from scene_images import prepare_scene_image
from product_ads import ad_for_language, append_silent_card

if os.environ.get("CODEX_PROXY_CERT"):
    proxy_cert = Path(os.environ["CODEX_PROXY_CERT"])
    ssl_context = getattr(edge_tts.communicate, "_SSL_CTX", None)
    if ssl_context is not None:
        ssl_context.load_verify_locations(str(proxy_cert))
    else:
        # edge-tts 7.2+ creates a fresh context from certifi for each stream.
        # Extend that trusted bundle without disabling TLS verification.
        import certifi

        combined_bundle = Path(tempfile.gettempdir()) / "midnight-anomaly-ca-bundle.pem"
        combined_bundle.write_bytes(
            Path(certifi.where()).read_bytes() + b"\n" + proxy_cert.read_bytes()
        )
        edge_tts.communicate.certifi.where = lambda: str(combined_bundle)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
SIZE = (1080, 1920)
FPS = 30
VOICES = {
    "zh": ("zh-CN-YunyangNeural", "-12%", "-10Hz"),
    "en": ("en-US-AndrewNeural", "-15%", "-8Hz"),
}
ECHO = {
    "zh": "aecho=0.8:0.88:48|87:0.045|0.025",
    "en": "aecho=0.8:0.88:48|87:0.035|0.02",
}


def run(*args: object, capture: bool = False) -> str:
    cmd = [str(x) for x in args]
    print("RUN", " ".join(cmd), flush=True)
    result = subprocess.run(cmd, check=True, text=True, capture_output=capture)
    return result.stdout if capture else ""


def probe_duration(path: Path) -> float:
    return float(
        run(
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
            capture=True,
        ).strip()
    )


def safe_file(value: str) -> Path:
    rel = Path(value)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"Unsafe path: {value}")
    path = ROOT / rel
    if not path.is_file():
        raise FileNotFoundError(f"Missing scene image: {value}")
    return path


def ass_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int(seconds // 60) % 60
    sec = seconds % 60
    return f"{hours}:{minutes:02}:{sec:05.2f}"


def ass_escape(text: str) -> str:
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace("{", "(")
        .replace("}", ")")
        .replace("\n", " ")
    )


def wrap_phrase(text: str, lang: str) -> str:
    """Limit captions to two centered lines in a 9:16 Shorts-safe column."""
    text = re.sub(r"\\s+", " ", str(text)).strip()
    width = 17 if lang == "zh" else 32
    if lang == "zh":
        # CJK has no spaces; textwrap with break_long_words=False never broke it.
        lines = [text[i:i + width] for i in range(0, len(text), width)]
    else:
        lines = textwrap.wrap(text, width=width, break_long_words=True,
                              break_on_hyphens=False)
    if len(lines) > 2:
        # Preserve all text for narration; avoid silently discarding captions.
        # Long segments should be split into separate timed captions instead.
        return "\\N".join(lines)
    return "\\N".join(lines)


def phrase_rows(data: dict, lang: str, story_seconds: float) -> list[tuple[float, float, str]]:
    segments = data.get("segments") or []
    phrases = [str(x[lang]).strip() for x in segments if str(x.get(lang, "")).strip()]
    if not phrases:
        phrases = [str(data[f"story_{lang}"]).strip()]
    captions = []
    for phrase in phrases:
        wrapped = wrap_phrase(phrase, lang).split("\\N")
        for i in range(0, len(wrapped), 2):
            captions.append("\\N".join(wrapped[i:i + 2]))
    weights = [max(1, len(re.sub(r"\\s+", "", x.replace("\\N", "")))) for x in captions]
    total_weight = sum(weights)
    elapsed = 0
    rows = []
    for caption, weight in zip(captions, weights):
        start = story_seconds * elapsed / total_weight
        elapsed += weight
        end = story_seconds * elapsed / total_weight
        rows.append((start, end, caption))
    return rows


def write_ass(
    data: dict,
    lang: str,
    story_seconds: float,
    total_seconds: float,
    path: Path,
) -> None:
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Channel,Noto Sans CJK TC,34,&H00D4D4D4,&H00FFFFFF,&H00101010,&H60000000,0,0,0,0,100,100,0,0,1,2,1,8,60,180,70,1
Style: Title,Noto Sans CJK TC,58,&H00E9D6A4,&H00FFFFFF,&H00101010,&H80000000,1,0,0,0,100,100,0,0,1,4,2,2,70,180,720,1
Style: Body,Noto Sans CJK TC,49,&H00FFFFFF,&H00FFFFFF,&H00101010,&H98000000,1,0,0,0,100,100,0,0,1,4,2,2,70,180,540,1
Style: PromoTitle,Noto Sans CJK TC,48,&H00E9D6A4,&H00FFFFFF,&H00101010,&H80000000,1,0,0,0,100,100,0,0,1,4,2,2,70,180,690,1
Style: Promo,Noto Sans CJK TC,52,&H00FFFFFF,&H00FFFFFF,&H00101010,&H98000000,1,0,0,0,100,100,0,0,1,4,2,2,70,180,520,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    title = data["title_zh" if lang == "zh" else "title_en"]
    promo = data.get("en_promo", {}) if lang == "en" else {}
    title_end = story_seconds if promo.get("enabled") else total_seconds
    events = [
        f"Dialogue: 0,{ass_time(0)},{ass_time(total_seconds)},Channel,,0,0,0,,MIDNIGHT ANOMALY / 午夜異常廣播",
        f"Dialogue: 0,{ass_time(0)},{ass_time(title_end)},Title,,0,0,0,,{{\\an5\\pos(540,1010)}}{ass_escape(title)}",
    ]
    for start, end, phrase in phrase_rows(data, lang, story_seconds):
        body_text = ass_escape(phrase).replace("\\\\N", "\\N")
        events.append(
            f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Body,,0,0,0,,{{\\an5\\pos(500,1280)}}{body_text}"
        )
    if promo.get("enabled"):
        promo_start = story_seconds + float(promo.get("pause_seconds", 0.75))
        promo_text = wrap_phrase(str(promo["voice_text"]), "en")
        promo_account = ass_escape(str(promo.get("display_account", "IG @speakoutnow88")))
        events.append(
            f"Dialogue: 1,{ass_time(promo_start)},{ass_time(total_seconds)},PromoTitle,,0,0,0,,{{\\an5\\pos(540,1010)}}English Course Promotion\\N英文課程推廣 · {promo_account}"
        )
        promo_ass_text = ass_escape(promo_text).replace("\\\\N", "\\N")
        events.append(
            f"Dialogue: 1,{ass_time(promo_start)},{ass_time(total_seconds)},Promo,,0,0,0,,{{\\an5\\pos(500,1280)}}{promo_ass_text}"
        )
    path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")


async def save_tts(text: str, lang: str, output: Path) -> None:
    voice, rate, pitch = VOICES[lang]
    await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(str(output))


def add_horror_ambience(narration: Path, temp: Path) -> Path:
    """Mix a very quiet, filtered brown-noise bed under the existing narration."""
    if os.environ.get("MIDNIGHT_AMBIENCE_ENABLED", "1") == "0":
        return narration
    mixed = temp / (narration.stem + "-ambience.wav")
    run(
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", narration,
        "-f", "lavfi", "-i",
        "anoisesrc=color=brown:amplitude=0.035:sample_rate=24000:seed=2710",
        "-filter_complex",
        "[1:a]highpass=f=45,lowpass=f=650,volume=0.20[bed];"
        "[0:a][bed]amix=inputs=2:duration=first:dropout_transition=0:"
        "normalize=0,alimiter=limit=0.95[mix]",
        "-map", "[mix]", "-c:a", "pcm_s16le", mixed,
    )
    return mixed


async def build_audio(data: dict, lang: str, temp: Path) -> tuple[Path, float, float]:
    raw_story = OUT / f"{lang}-raw-story.mp3"
    started = time.perf_counter()
    reuse_tts = os.environ.get("MIDNIGHT_REUSE_TTS") == "1"
    if not (reuse_tts and raw_story.is_file()):
        await save_tts(str(data[f"story_{lang}"]), lang, raw_story)
    tts_seconds = time.perf_counter() - started
    decoded_story = temp / f"{lang}-story.wav"
    run(
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        raw_story,
        "-c:a",
        "pcm_s16le",
        decoded_story,
    )
    story_seconds = probe_duration(decoded_story)
    inputs: list[object] = ["-i", raw_story]
    source = "[0:a]"
    if lang == "en" and data.get("en_promo", {}).get("enabled"):
        promo = data["en_promo"]
        raw_promo = OUT / "en-raw-promo.mp3"
        if not (reuse_tts and raw_promo.is_file()):
            await save_tts(str(promo["voice_text"]), "en", raw_promo)
        pause = float(promo.get("pause_seconds", 0.75))
        inputs = [
            "-i",
            raw_story,
            "-f",
            "lavfi",
            "-t",
            f"{pause:.3f}",
            "-i",
            "anullsrc=r=24000:cl=mono",
            "-i",
            raw_promo,
        ]
        source = "[0:a][1:a][2:a]concat=n=3:v=0:a=1"
    narration = OUT / f"{lang}-narration.wav"
    separator = "," if "concat=" in source else ""
    audio_filter = (
        f"{source}{separator}highpass=f=65,lowpass=f=10000,{ECHO[lang]},"
        "loudnorm=I=-18:TP=-1.5:LRA=7[mix]"
    )
    run(
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        *inputs,
        "-filter_complex",
        audio_filter,
        "-map",
        "[mix]",
        "-c:a",
        "pcm_s16le",
        narration,
    )
    narration = add_horror_ambience(narration, temp)
    return narration, story_seconds, tts_seconds


def render_video(
    data: dict,
    lang: str,
    audio: Path,
    story_seconds: float,
    temp: Path,
) -> tuple[Path, float]:
    total = probe_duration(audio)
    if not 60 <= total <= 90:
        raise ValueError(f"{lang} duration {total:.3f}s outside 60-90s")
    scenes = data["assets"]["images"]
    segment_seconds = total / len(scenes)
    clips: list[Path] = []
    for index, scene in enumerate(scenes):
        image = safe_file(scene["file"])
        base = temp / f"{lang}-base-{index:02}.png"
        prepare_scene_image(image, base, SIZE)
        frames = max(1, math.ceil(segment_seconds * FPS))
        effect = scene.get("effect", "slow_zoom")
        if effect == "static":
            visual = "scale=1080:1920,format=yuv420p"
        elif effect == "pan_left":
            visual = f"zoompan=z=1.12:x=(iw-iw/zoom)*(1-on/{frames}):y=(ih-ih/zoom)/2:d={frames}:s=1080x1920:fps=30,format=yuv420p"
        elif effect == "pan_right":
            visual = f"zoompan=z=1.12:x=(iw-iw/zoom)*(on/{frames}):y=(ih-ih/zoom)/2:d={frames}:s=1080x1920:fps=30,format=yuv420p"
        else:
            visual = f"zoompan=z=min(zoom+0.00032\\,1.10):d={frames}:s=1080x1920:fps=30,format=yuv420p"
        effects = scene.get("effects", [])
        if "film_grain" in effects:
            visual += ",noise=alls=5:allf=t"
        if "flicker" in effects:
            visual += ",eq=brightness=0.025*sin(0.31*n)"
        clip = temp / f"{lang}-clip-{index:02}.mp4"
        run(
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-loop",
            "1",
            "-i",
            base,
            "-vf",
            visual,
            "-frames:v",
            frames,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "25",
            "-an",
            clip,
        )
        clips.append(clip)
    manifest = temp / f"{lang}-clips.txt"
    manifest.write_text("".join(f"file '{p.as_posix()}'\n" for p in clips), encoding="utf-8")
    subtitles = OUT / f"{lang}.ass"
    write_ass(data, lang, story_seconds, total, subtitles)
    output = OUT / f"{lang}.mp4"
    started = time.perf_counter()
    run(
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        manifest,
        "-i",
        audio,
        "-vf",
        (
            f"ass='{subtitles.as_posix()}':fontsdir='{(ROOT / 'assets' / 'common').as_posix()}',"
            "scale=in_range=full:out_range=tv,format=yuv420p"
        ),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-t",
        f"{total:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "24",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(FPS),
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-movflags",
        "+faststart",
        output,
    )
    ad = ad_for_language(data, lang)
    if ad:
        if total + float(ad["duration_seconds"]) > 90:
            raise ValueError("Story plus product ad exceeds 90s; shorten the story before rendering")
        card = append_silent_card(output, ad, temp)
        (OUT / "product-ad.png").write_bytes(card.read_bytes())
    return output, time.perf_counter() - started


async def main_async() -> None:
    started = time.perf_counter()
    data = json.loads((ROOT / "stories" / "today.json").read_text(encoding="utf-8"))
    if os.environ.get("DAILY_AD_JOB_FILE"):
        from ai_ad_job import apply_job
        data = apply_job(data, Path(os.environ["DAILY_AD_JOB_FILE"]))
    elif os.environ.get("PRODUCT_AD_FILE"):
        data["product_ad"] = json.loads(Path(os.environ["PRODUCT_AD_FILE"]).read_text(encoding="utf-8"))
    product_ad = ad_for_language(data, "zh")
    if not data.get("story_id"):
        raise ValueError("story_id is required")
    if not 6 <= len(data.get("assets", {}).get("images", [])) <= 8:
        raise ValueError("Exactly 6-8 real scene images are required")
    OUT.mkdir(exist_ok=True)
    metrics = {
        "story_id": data["story_id"],
        "token_usage": None,
        "token_usage_note": "Exact model token usage is not available in GitHub Actions.",
        "languages": {},
        "product_ad": ({"enabled": True, "language": "zh", "voiceover": False,
                        "duration_seconds": product_ad["duration_seconds"],
                        "product_id": product_ad["product"]["id"]} if product_ad else {"enabled": False}),
    }
    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        for lang in ("zh", "en"):
            audio, story_seconds, tts_seconds = await build_audio(data, lang, temp)
            output, render_seconds = render_video(data, lang, audio, story_seconds, temp)
            metrics["languages"][lang] = {
                "tts_seconds": round(tts_seconds, 3),
                "story_audio_seconds": round(story_seconds, 3),
                "output_seconds": round(probe_duration(output), 3),
                "render_seconds": round(render_seconds, 3),
                "output_bytes": output.stat().st_size,
            }
    metrics["total_wall_seconds"] = round(time.perf_counter() - started, 3)
    (OUT / "build-performance.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    asyncio.run(main_async())
