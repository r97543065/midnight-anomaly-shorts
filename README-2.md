# Midnight Anomaly Shorts / 午夜異常廣播

GitHub Actions bilingual Shorts production scaffold. The existing `free-tts-test.yml` can stay in your repository; this package adds the new workflow.

## Directory layout

```text
.github/workflows/daily-shorts.yml   GitHub Actions build (manual or JSON push)
stories/today.json                   Active episode script
scripts/make_video.py               Edge TTS + FFmpeg renderer
assets/episodes/YYYYMMDD/           Episode-specific scene images (upload later)
assets/common/music/                Licensed background music (upload later)
assets/common/sfx/                  Licensed sound effects (upload later)
docs/episode-format.example.json     Proposed future JSON with asset paths
output/                              Generated MP3/MP4 (ignored by Git; uploaded as Actions artifact)
```

## First test

1. Copy this folder's **contents** to the root of `r97543065/midnight-anomaly-shorts` on `main`.
2. Commit the files. Updating `stories/today.json` triggers `daily-shorts.yml` automatically.
3. Alternatively: Actions > Build bilingual horror shorts > Run workflow.
4. Download `bilingual-shorts-<run_id>` from the completed run's Artifacts.

**Current implementation:** reads `date`, `title_zh`, `title_en`, `story_zh`, `story_en` from `stories/today.json`; generates zh/en MP3 and black-background MP4. The `assets/` directories and `docs/episode-format.example.json` are a **future asset layout**, not yet consumed by `make_video.py`. Do not expect pictures, music, subtitles, or YouTube uploads in this version. Image files must be uploaded separately before an image-aware renderer can use them.

No OpenAI API is used. GitHub connector write permission is not needed if you push files manually.
