#!/usr/bin/env python3
"""Select a verified affiliate offer and render a silent, post-story ad card.

The feed is an explicit integration boundary, not a guessed Shopee API endpoint.
Only the operator's approved affiliate data source may populate it.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from functools import lru_cache
from urllib.parse import urlencode, urlparse
from urllib.request import Request

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
MAX_AGE_HOURS = 24


def https_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Affiliate data URLs must use HTTPS without embedded credentials")
    return value


def timestamp(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Offer timestamps must include a timezone")
    return result


def validate_offer(product: dict, now: datetime | None = None, *, require_fresh: bool = True) -> dict:
    now = now or datetime.now(timezone.utc)
    for field in ("id", "name", "affiliate_url", "verified_at", "expires_at", "source"):
        if not isinstance(product.get(field), str) or not product[field].strip():
            raise ValueError(f"Offer requires {field}")
    if product.get("market") != "TW" or product.get("affiliate_eligible") is not True:
        raise ValueError("Offer must be a verified TW affiliate product")
    if product.get("available") is not True:
        raise ValueError("Offer must be available")
    host = urlparse(https_url(product["affiliate_url"])).hostname
    if host not in {"shopee.tw", "www.shopee.tw", "s.shopee.tw", "shope.ee"}:
        raise ValueError("Offer link must be a Shopee tracking link from the approved source")
    verified, expires = timestamp(product["verified_at"]), timestamp(product["expires_at"])
    age = (now - verified).total_seconds()
    if expires <= verified or expires <= now or age < -300 or (require_fresh and age > MAX_AGE_HOURS * 3600):
        raise ValueError("Offer is stale, expired, or has invalid timestamps")
    # A URL alone does not establish eligibility: require upstream verification above.
    if not isinstance(product.get("keywords"), list) or not product["keywords"]:
        raise ValueError("Offer requires story-matching keywords")
    for field in ("name", "benefit_zh"):
        if field in product and (not isinstance(product[field], str) or len(product[field]) > 120):
            raise ValueError(f"Invalid {field}")
    if product.get("commission_rate") is not None:
        rate = float(product["commission_rate"])
        if not math.isfinite(rate) or not 0 <= rate <= 1:
            raise ValueError("commission_rate must be a fraction between 0 and 1")
    return product


def load_feed(story: dict, feed: str | None) -> dict:
    if feed:
        return json.loads(Path(feed).read_text(encoding="utf-8"))
    endpoint = os.environ.get("SHOPEE_AFFILIATE_FEED_URL", "")
    if not endpoint:
        raise ValueError("Missing approved affiliate feed. Configure SHOPEE_AFFILIATE_FEED_URL or --feed; no ad generated.")
    https_url(endpoint)
    if urlparse(endpoint).query or urlparse(endpoint).fragment:
        raise ValueError("Use a query-free feed URL; store credentials in the token secret")
    # The authorized adapter performs live affiliate-product search for this episode.
    query = urlencode({"market": "TW", "story_id": story["story_id"],
                       "q": story["title_zh"], "limit": 30})
    headers = {"Accept": "application/json"}
    if os.environ.get("SHOPEE_AFFILIATE_FEED_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["SHOPEE_AFFILIATE_FEED_TOKEN"]
    # No redirects: never forward credentials to an unexpected endpoint.
    from urllib.request import HTTPRedirectHandler, build_opener

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    request = Request(endpoint + "?" + query, headers=headers)
    with build_opener(NoRedirect).open(request, timeout=30) as response:
        payload = response.read(2_000_001)
    if len(payload) > 2_000_000:
        raise ValueError("Affiliate feed exceeds size limit")
    return json.loads(payload)


def select_offer(story: dict, feed: dict, now: datetime | None = None, *, require_fresh: bool = True) -> dict:
    text = (story.get("title_zh", "") + " " + story.get("story_zh", "")).lower()
    candidates = []
    for product in feed.get("products", []):
        try:
            validate_offer(product, now, require_fresh=require_fresh)
            score = sum(len(str(k)) for k in product["keywords"]
                        if len(str(k).strip()) >= 2 and str(k).lower() in text)
            if score:
                candidates.append((score, product["id"], product))
        except (ValueError, TypeError, KeyError):
            continue
    if not candidates:
        raise ValueError("No unexpired, eligible, story-relevant affiliate offers. No ad generated.")
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


def validate_ad(ad: dict, story: dict | None = None, *, require_fresh: bool = True) -> dict:
    if ad.get("status") != "verified" or ad.get("voiceover") is not False:
        raise ValueError("Product ad must be verified and have voiceover=false")
    if ad.get("language", "zh") != "zh":
        raise ValueError("Product ads currently support Chinese videos only")
    if story and ad.get("story_id") != story.get("story_id"):
        raise ValueError("Product ad belongs to another story")
    duration = float(ad.get("duration_seconds", 8))
    if not math.isfinite(duration) or not 5 <= duration <= 12:
        raise ValueError("Product card must last 5-12 seconds")
    validate_offer(ad["product"], require_fresh=require_fresh)
    for field in ("headline", "ad_copy_zh", "slogan", "cta", "disclosure"):
        if not isinstance(ad.get(field), str) or not ad[field].strip():
            raise ValueError(f"Product ad requires {field}")
    return ad


def ad_for_language(data: dict, lang: str, *, require_fresh: bool = True) -> dict | None:
    ad = data.get("product_ad", {})
    if lang != "zh" or not ad.get("enabled"):
        return None
    return validate_ad(ad, data, require_fresh=require_fresh)


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
        # Keep every glyph inside the designated horizontal/vertical safe area.
        bounds = draw.textbbox((90, y), line, font=face)
        if bounds[0] < 70 or bounds[2] > 1010 or bounds[1] < 180 or bounds[3] > 1740:
            raise ValueError("Product card text exceeds visual safe area")
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
    end_name = draw_text(draw, ad["product"]["name"], 600, 62, "#d6bd83", max_lines=3)
    if end_name > 895:
        raise ValueError("Product name overlaps description")
    end_copy = draw_text(draw, ad["ad_copy_zh"], 900, 42, max_lines=3)
    if end_copy > 1115:
        raise ValueError("Product description overlaps slogan")
    end_slogan = draw_text(draw, ad["slogan"], 1120, 40, "#d6bd83", max_lines=2)
    if end_slogan > 1325:
        raise ValueError("Product slogan overlaps CTA")
    draw_text(draw, ad["cta"], 1330, 35, max_lines=2)
    draw_text(draw, ad["disclosure"], 1550, 29, "#b8c1c6", max_lines=2)
    image.save(target)


def append_silent_card(video: Path, ad: dict, temp: Path) -> Path:
    """Append after all story frames/audio. Never send ad text to TTS."""
    validate_ad(ad)
    card = temp / "product-ad.png"
    if ad.get("card_image"):
        source = (ROOT / ad["card_image"]).resolve()
        if not source.is_relative_to((ROOT / "assets").resolve()) or not source.is_file():
            raise ValueError("Invalid AI card image path")
        with Image.open(source) as source_image:
            if source_image.size != (1080, 1920):
                raise ValueError("AI card image must be 1080x1920")
            source_image.convert("RGB").save(card)
    else:
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
    # Publication freshness is checked separately before using this snapshot.
    validate_ad(ad, require_fresh=False)
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
