"""Real FFmpeg smoke: a short tone followed by an eight-second silent card."""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from product_ads import append_silent_card, make_ad
from test_product_ads import STORY, fixture


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True)


def main():
    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        video = temp / "test.mp4"
        run("ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "color=c=gray:s=1080x1920:r=30:d=2",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=2",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(video))
        ad = make_ad(STORY, fixture())
        append_silent_card(video, ad, temp)
        probe = json.loads(run("ffprobe", "-v", "error", "-show_format", "-show_streams",
                               "-of", "json", str(video)).stdout)
        duration = float(probe["format"]["duration"])
        assert 9.9 <= duration <= 10.2, duration
        assert any(x.get("width") == 1080 and x.get("height") == 1920 for x in probe["streams"])
        for start, expected_silence in [(0.25, False), (3, True)]:
            volume = run("ffmpeg", "-hide_banner", "-ss", str(start), "-i", str(video),
                         "-t", "1", "-af", "volumedetect", "-vn", "-f", "null", "-")
            peak = float(re.search(r"max_volume:\s*(-?inf|-?[0-9.]+) dB", volume.stderr).group(1))
            assert (peak < -80) == expected_silence, (start, peak)
        run("ffmpeg", "-v", "error", "-i", str(video), "-f", "null", "-")
        # Stable local review output; explicitly synthetic and never uploaded.
        preview = Path(__file__).resolve().parents[1] / "output/test-product-ad.png"
        preview.parent.mkdir(exist_ok=True)
        preview.write_bytes((temp / "product-ad.png").read_bytes())
        print(f"PASS: {duration:.3f}s MP4, 1080x1920, original tone preserved, product card silent")


if __name__ == "__main__":
    main()
