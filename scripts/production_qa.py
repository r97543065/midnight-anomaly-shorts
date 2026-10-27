#!/usr/bin/env python3
"""Decode and inspect both finished videos, then emit a machine-readable report."""
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from product_ads import ad_for_language

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
STORY = ROOT / "stories" / "today.json"
MIN_SECONDS = 60
MAX_SECONDS = 90


def command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True)


def media_probe(path: Path) -> dict:
    result = command(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=index,codec_type,codec_name,width,height,pix_fmt,r_frame_rate",
            "-of",
            "json",
            str(path),
        ]
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "ffprobe failed")
    return json.loads(result.stdout)


def qa_video(path: Path) -> tuple[dict, list[str], list[str]]:
    problems: list[str] = []
    warnings: list[str] = []
    if not path.is_file():
        return {"file": str(path.relative_to(ROOT))}, ["missing video"], warnings
    try:
        probe = media_probe(path)
    except Exception as exc:
        return {"file": str(path.relative_to(ROOT))}, [f"ffprobe: {exc}"], warnings
    duration = round(float(probe["format"]["duration"]), 3)
    streams = probe.get("streams", [])
    video = next((x for x in streams if x.get("codec_type") == "video"), {})
    audio = next((x for x in streams if x.get("codec_type") == "audio"), {})
    checks = {
        "duration_target": MIN_SECONDS <= duration <= MAX_SECONDS,
        "video_codec": video.get("codec_name") == "h264",
        "dimensions": (video.get("width"), video.get("height")) == (1080, 1920),
        "pixel_format": video.get("pix_fmt") == "yuv420p",
        "fps": video.get("r_frame_rate") in {"30/1", "60/2"},
        "audio_codec": audio.get("codec_name") == "aac",
    }
    for name, passed in checks.items():
        if not passed:
            problems.append(f"{name} failed")
    decode = command(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"])
    checks["full_decode"] = decode.returncode == 0
    if decode.returncode:
        problems.append("full decode failed")
    black = command(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(path),
            "-vf",
            "blackdetect=d=0.50:pix_th=0.02",
            "-an",
            "-f",
            "null",
            "-",
        ]
    )
    black_intervals = re.findall(r"black_start:[^\s]+\s+black_end:[^\s]+", black.stderr)
    if black_intervals:
        warnings.append(f"black intervals: {black_intervals}")
    volume = command(
        ["ffmpeg", "-hide_banner", "-i", str(path), "-af", "volumedetect", "-vn", "-f", "null", "-"]
    )
    peak_match = re.search(r"max_volume:\s*(-?[0-9.]+) dB", volume.stderr)
    peak_dbfs = float(peak_match.group(1)) if peak_match else None
    if peak_dbfs is None:
        warnings.append("audio peak unavailable")
    elif peak_dbfs >= 0:
        problems.append("audio clipping risk")
    return (
        {
            "file": str(path.relative_to(ROOT)),
            "size_bytes": path.stat().st_size,
            "duration_seconds": duration,
            "video": video,
            "audio": audio,
            "checks": checks,
            "black_intervals": black_intervals,
            "audio_peak_dbfs": peak_dbfs,
        },
        problems,
        warnings,
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    problems: list[str] = []
    warnings: list[str] = []
    try:
        story = json.loads(STORY.read_text(encoding="utf-8"))
        images = story.get("assets", {}).get("images", [])
        if not 6 <= len(images) <= 8:
            problems.append(f"scene count {len(images)} is not 6-8")
        for scene in images:
            rel = Path(scene.get("file", ""))
            if rel.is_absolute() or ".." in rel.parts or not (ROOT / rel).is_file():
                problems.append(f"missing or unsafe image: {rel}")
        promo = story.get("en_promo", {})
        if promo.get("enabled") and "@speakoutnow88" not in promo.get("display_account", ""):
            problems.append("English promotion account mismatch")
    except Exception as exc:
        story = {}
        problems.append(f"invalid story JSON: {exc}")
    videos = {}
    for lang in ("zh", "en"):
        result, lang_problems, lang_warnings = qa_video(OUT / f"{lang}.mp4")
        videos[lang] = result
        problems.extend(f"{lang}: {x}" for x in lang_problems)
        warnings.extend(f"{lang}: {x}" for x in lang_warnings)
        if not (OUT / f"{lang}.ass").is_file():
            problems.append(f"{lang}: missing burned-caption source")
    build_result = os.environ.get("BUILD_RESULT", "success")
    if build_result != "success":
        problems.append(f"build step: {build_result}")
    ad_report = {"enabled": False}
    try:
        if os.environ.get("PRODUCT_AD_FILE"):
            story["product_ad"] = json.loads(Path(os.environ["PRODUCT_AD_FILE"]).read_text(encoding="utf-8"))
        ad = ad_for_language(story, "zh")
        performance = {}
        if (OUT / "build-performance.json").is_file():
            performance = json.loads((OUT / "build-performance.json").read_text(encoding="utf-8"))
        if bool(performance.get("product_ad", {}).get("enabled")) != bool(ad):
            raise ValueError("Rendered ad and requested ad disagree")
        if ad:
            built = performance.get("product_ad", {})
            if not built.get("enabled") or built.get("product_id") != ad["product"]["id"]:
                raise ValueError("Ad does not match build metrics")
            if performance.get("story_id") != story.get("story_id"):
                raise ValueError("Ad build belongs to another story")
            duration = float(ad["duration_seconds"])
            total = videos["zh"]["duration_seconds"]
            # Confirm actual silence in the final card, excluding the AAC boundary.
            tail = command(["ffmpeg", "-hide_banner", "-ss", str(total-duration+0.25),
                            "-i", str(OUT / "zh.mp4"), "-t", str(duration-0.5),
                            "-af", "volumedetect", "-vn", "-f", "null", "-"])
            peak = re.search(r"max_volume:\s*(-?inf|-?[0-9.]+) dB", tail.stderr)
            silent = tail.returncode == 0 and peak is not None and float(peak.group(1)) <= -80
            if not silent:
                raise ValueError("Product ad audio is not silent")
            ad_report = {"enabled": True, "product_id": ad["product"]["id"],
                         "duration_seconds": duration, "voiceover": False,
                         "silence_check": "passed"}
    except Exception as exc:
        problems.append(f"product ad QA: {exc}")
    status = "failure" if problems else ("warning" if warnings else "success")
    report = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "story_id": story.get("story_id"),
        "episode_date": story.get("date"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "commit_sha": os.environ.get("GITHUB_SHA"),
        "run_url": (
            f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/"
            f"{os.environ.get('GITHUB_REPOSITORY', '')}/actions/runs/"
            f"{os.environ.get('GITHUB_RUN_ID', '')}"
        ),
        "build_result": build_result,
        "qa_status": status,
        "scene_count": len(story.get("assets", {}).get("images", [])),
        "videos": videos,
        "product_ad": ad_report,
        "errors": problems,
        "warnings": warnings,
        "manual_review_required": [
            "caption visual safe area",
            "narration pronunciation and semantic completeness",
            "image continuity and story fit",
        ],
    }
    (OUT / "production-status.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    summary = [
        "## Midnight Anomaly production QA",
        f"**Result:** {status.upper()} | **Build:** {build_result}",
        f"**Story:** {report['story_id']} | **Run:** {report['run_id']}",
        "",
        "| Language | Duration | Peak |",
        "|---|---:|---:|",
    ]
    for lang, item in videos.items():
        summary.append(
            f"| {lang} | {item.get('duration_seconds', 'missing')} s | "
            f"{item.get('audio_peak_dbfs', 'unknown')} dBFS |"
        )
    if problems:
        summary.extend(["", "### Errors", *[f"- {x}" for x in problems]])
    if warnings:
        summary.extend(["", "### Warnings", *[f"- {x}" for x in warnings]])
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write("\n".join(summary) + "\n")
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
