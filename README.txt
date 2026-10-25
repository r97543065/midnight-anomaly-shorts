V3 FFmpeg patch
1. Copy scripts/make_video.py into your repository, replacing the existing file.
2. Commit and push to main. Existing daily-shorts.yml triggers automatically.
3. Check Actions artifact midnight-shorts-v2 (workflow artifact name remains unchanged).
New optional JSON fields per scene: effect = slow_zoom|static|pan_left|pan_right; effects = [film_grain, flicker].
Optional assets.music path enables background music at 12% volume.
ASS phrase captions are estimated from text length, not synchronized to actual spoken word boundaries.
Scene images are still provided separately. Existing today.json remains compatible.
