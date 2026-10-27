#!/usr/bin/env python3
"""Build two reproducible 9:16 horror shorts from stories/today.json."""
from __future__ import annotations

import asyncio
import json
import math
import os
import re
import subprocess
import tempfile
import textwrap
import time
from pathlib import Path

import edge_tts
from PIL import Image
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
        with Image.open(image) as source:
            source = source.convert("RGB")
            scale = max(SIZE[0] / source.width, SIZE[1] / source.height)
            resized = source.resize(
                (math.ceil(source.width * scale), math.ceil(source.height * scale)),
                Image.Resampling.LANCZOS,
            )
            left = (resized.width - SIZE[0]) // 2
            top = (resized.height - SIZE[1]) // 2
            base = temp / f"{lang}-base-{index:02}.jpg"
            resized.crop((left, top, left + SIZE[0], top + SIZE[1])).save(base, quality=92)
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
     …2293 tokens truncated… story.get("story_zh", "")).lower()
    candidates = []
    for product in feed.get("products", []):
        try:
            validate_offer(product, now)
            score = sum(len(str(k)) for k in product["keywords"]
                        if len(str(k).strip()) >= 2 and str(k).lower() in text)
            if score:
                candidates.append((score, product["id"], product))
        except (ValueError, TypeError, KeyError):
            continue
    if not candidates:
        raise ValueError("No fresh, eligible, story-relevant affiliate offers. No ad generated.")
    return sorted(candidates, key=lambda x: (-x[0], x[1]))[0][2]


def make_ad(story: dict, product: dict) -> dict:
    name = product["name"]
    # Product facts come only from the approved feed. No invented discounts or claims.
    benefit = product.get("benefit_zh", "")
    return {
        "enabled": True, "status": "verified", "language": "zh",
        "duration_seconds": 8, "voiceover": False,
        "story_id": story["story_id"], "product": product,
        "headline": "故事結束了，日常還在繼續。",
        "ad_copy_zh": benefit or f"今天的故事選物：{name}。",
        "slogan": f"把{name}，留給真實的日常。",
        "cta": "商品分潤連結請見影片說明",
        "disclosure": "商品推廣｜透過連結購買，我可能獲得分潤",
    }


def validate_ad(ad: dict, story: dict | None = None) -> dict:
    if ad.get("status") != "verified" or ad.get("voiceover") is not False:
        raise ValueError("Product ad must be verified and have voiceover=false")
    if ad.get("language", "zh") != "zh":
        raise ValueError("Product ads currently support Chinese videos only")
    if story and ad.get("story_id") != story.get("story_id"):
        raise ValueError("Product ad belongs to another story")
    duration = float(ad.get("duration_seconds", 8))
    if not math.isfinite(duration) or not 5 <= duration <= 12:
        raise ValueError("Product card must last 5-12 seconds")
    validate_offer(ad["product"])
    for field in ("headline", "ad_copy_zh", "slogan", "cta", "disclosure"):
        if not isinstance(ad.get(field), str) or not ad[field].strip():
            raise ValueError(f"Product ad requires {field}")
    return ad


def ad_for_language(data: dict, lang: str) -> dict | None:
    ad = data.get("product_ad", {})
    if lang != "zh" or not ad.get("enabled"):
        return None
    return validate_ad(ad, data)


@lru_cache(maxsize=16)
def font(size: int) -> ImageFont.FreeTypeFont:
    path = os.environ.get("PRODUCT_AD_FONT")
    if not path:
        path = subprocess.check_output(
            ["fc-match", "-f", "%{file}", "Noto Sans CJK TC"], text=True).strip()
    loaded = ImageFont.truetype(path, size)
    # Fail rather than publish a card containing missing-glyph boxes.
    if "Noto" not in loaded.getname()[0] and not os.environ.get("PRODUCT_AD_FONT"):
        raise ValueError("Install fonts-noto-cjk or set PRODUCT_AD_FONT to a CJK font")
    return loaded


@lru_cache(maxsize=8)
def font_characters(path: str) -> frozenset[int]:
    from fontTools.ttLib import TTFont
    with TTFont(path, fontNumber=0) as source:
        return frozenset(source.getBestCmap())


def draw_text(draw, text, y, size=48, color="#eee9df", max_lines=3):
    face = font(size)
    missing = sorted({c for c in text if not c.isspace() and ord(c) not in font_characters(face.path)})
    if missing:
        raise ValueError("Product card font is missing characters: " + "".join(missing))
    lines, line = [], ""
    for char in text:
        if char == "\n" or draw.textlength(line + char, font=face) > 800:
            lines.append(line)
            line = "" if char == "\n" else char
        else:
            line += char
    if line:
        lines.append(line)
    if len(lines) > max_lines:
        raise ValueError("Product card text is too long; shorten the source copy")
    for line in lines:
        draw.text((90, y), line, font=face, fill=color)
        y += int(size * 1.45)
    return y


def render_card(ad: dict, target: Path) -> None:
    validate_ad(ad)
    image = Image.new("RGB", (1080, 1920), "#11171c")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((60, 210, 940, 1490), radius=32, fill="#202a30")
    draw.rectangle((90, 320, 880, 326), fill="#d6bd83")
    draw_text(draw, "午夜異常廣播 · 故事後選物", 250, 34, "#d6bd83")
    draw_text(draw, ad["headline"], 390, 46, max_lines=2)
    draw_text(draw, ad["product"]["name"], 600, 62, "#d6bd83", max_lines=3)
    draw_text(draw, ad["ad_copy_zh"], 900, 42, max_lines=3)
    draw_text(draw, ad["slogan"], 1120, 40, "#d6bd83", max_lines=2)
    draw_text(draw, ad["cta"], 1330, 35, max_lines=2)
    draw_text(draw, ad["disclosure"], 1550, 29, "#b8c1c6", max_lines=2)
    image.save(target)


def append_silent_card(video: Path, ad: dict, temp: Path) -> Path:
    """Append after all story frames/audio. Never send ad text to TTS."""
    validate_ad(ad)
    card = temp / "product-ad.png"
    render_card(ad, card)
    duration = float(ad["duration_seconds"])
    result = temp / "zh-with-product-ad.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
        "-loop", "1", "-framerate", "30", "-i", str(card),
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
        "-filter_complex",
        f"[0:v]setsar=1,setpts=PTS-STARTPTS[v0];"
        f"[1:v]trim=duration={duration},format=yuv420p,setsar=1,setpts=PTS-STARTPTS[v1];"
        f"[0:a]aresample=48000,aformat=channel_layouts=stereo,asetpts=PTS-STARTPTS[a0];"
        f"[2:a]atrim=duration={duration},asetpts=PTS-STARTPTS[a1];"
        "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]",
        "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "24", "-r", "30", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-b:a", "160k", "-movflags", "+faststart", str(result),
    ], check=True)
    result.replace(video)
    return card


def description_suffix(ad: dict) -> str:
    validate_ad(ad)
    return (f"\n\n【故事後選物・商品推廣】\n{ad['product']['name']}\n"
            f"{ad['slogan']}\n{ad['product']['affiliate_url']}\n{ad['disclosure']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--story", default=str(ROOT / "stories/today.json"))
    parser.add_argument("--feed", help="Approved affiliate JSON export; otherwise query configured adapter")
    parser.add_argument("--out", default=str(ROOT / "output/product-ad.json"))
    parser.add_argument("--render-preview", action="store_true")
    args = parser.parse_args()
    story = json.loads(Path(args.story).read_text(encoding="utf-8"))
    target = Path(args.out)
    # Remove stale results before fetching. A failed selection cannot reuse yesterday's ad.
    target.unlink(missing_ok=True)
    target.with_suffix(".txt").unlink(missing_ok=True)
    target.with_suffix(".png").unlink(missing_ok=True)
    product = select_offer(story, load_feed(story, args.feed))
    ad = make_ad(story, product)
    validate_ad(ad, story)
    target.parent.mkdir(parents=True, exist_ok=True)
    if args.render_preview:
        render_card(ad, target.with_suffix(".png"))
    target.write_text(json.dumps(ad, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    target.with_suffix(".txt").write_text(
        ad["headline"] + "\n" + ad["ad_copy_zh"] + "\n" + ad["slogan"] + description_suffix(ad),
        encoding="utf-8")
    print(f"Generated silent product ad for {story['story_id']}; selected {product['id']}")


if __name__ == "__main__":
    main()
