#!/usr/bin/env python3
"""Post-build QA and machine-readable status for GitHub Actions."""
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
STORY = ROOT / "stories" / "today.json"
MIN_SECONDS = 60
MAX_SECONDS = 90

def probe(path):
    try:
        p = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, check=True,
        )
        return round(float(p.stdout.strip()), 2)
    except (OSError, ValueError, subprocess.CalledProcessError):
        return None

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    problems, warnings, videos = [], [], {}
    build_result = os.environ.get("BUILD_RESULT", "unknown")
    try:
        data = json.loads(STORY.read_text(encoding="utf-8"))
        images = data.get("assets", {}).get("images", [])
        if not images:
            problems.append("No scene images declared")
        for scene in images:
            rel = Path(scene["file"])
            if rel.is_absolute() or ".." in rel.parts or not (ROOT / rel).is_file():
                problems.append(f"Missing or unsafe image: {rel}")
        episode_date = data.get("date")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        episode_date = None
        problems.append(f"Invalid story JSON: {exc}")
    for lang in ("zh", "en"):
        video = OUT / f"{lang}.mp4"
        seconds = probe(video) if video.is_file() else None
        videos[lang] = {"file": f"output/{lang}.mp4", "duration_seconds": seconds}
        if seconds is None or seconds <= 0:
            problems.append(f"{lang}: missing or invalid video")
        elif not MIN_SECONDS <= seconds <= MAX_SECONDS:
            warnings.append(f"{lang}: {seconds}s outside target {MIN_SECONDS}-{MAX_SECONDS}s")
    if build_result != "success":
        problems.append(f"Build step: {build_result}")
    status = "failure" if problems else ("warning" if warnings else "success")
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "episode_date": episode_date,
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "commit_sha": os.environ.get("GITHUB_SHA"),
        "run_url": f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{os.environ.get('GITHUB_REPOSITORY', '')}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}",
        "build_result": build_result,
        "qa_status": status,
        "videos": videos,
        "errors": problems,
        "warnings": warnings,
    }
    (OUT / "production-status.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "## Midnight Anomaly production QA",
        f"**Result:** {status.upper()} | **Build:** {build_result}",
        f"**Episode:** {episode_date or 'unknown'} | **Run:** {report['run_id']}",
        "",
        "| Language | Duration |",
        "|---|---:|",
    ]
    for lang, item in videos.items():
        lines.append(f"| {lang} | {item['duration_seconds'] if item['duration_seconds'] is not None else 'missing'} s |")
    for label, items in (("Errors", problems), ("Warnings", warnings)):
        if items:
            lines.extend(["", f"### {label}"])
            lines.extend(f"- {item}" for item in items)
    summary = "\n".join(lines) + "\n"
    print(summary)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as fh:
            fh.write(summary)
    # A warning is informative; actual build errors and missing assets fail the job.
    if problems:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
