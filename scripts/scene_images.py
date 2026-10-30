"""Prepare PNG, JPEG, or WebP scenes for FFmpeg without intermediate JPEG loss."""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageOps

SUPPORTED_IMAGE_FORMATS = {"PNG", "JPEG", "WEBP"}


def prepare_scene_image(
    source_path: Path,
    output_path: Path,
    size: tuple[int, int] = (1080, 1920),
) -> None:
    """Center-crop a still image to the video frame using a lossless PNG intermediate.

    The final MP4 is still H.264; this only avoids introducing JPEG artifacts
    between decoding the source image and encoding the video.
    """
    with Image.open(source_path) as original:
        if original.format not in SUPPORTED_IMAGE_FORMATS:
            raise ValueError(
                f"Unsupported scene image format: {original.format!r} ({source_path}); "
                "use PNG, JPEG or WebP"
            )
        if getattr(original, "n_frames", 1) != 1:
            raise ValueError(f"Scene image must be a still image: {source_path}")

        oriented = ImageOps.exif_transpose(original)
        if "A" in oriented.getbands() or "transparency" in oriented.info:
            foreground = oriented.convert("RGBA")
            background = Image.new("RGBA", foreground.size, (0, 0, 0, 255))
            background.alpha_composite(foreground)
            source = background.convert("RGB")
        else:
            source = oriented.convert("RGB")

        width, height = size
        if width <= 0 or height <= 0:
            raise ValueError("Scene dimensions must be positive")
        scale = max(width / source.width, height / source.height)
        resized = source.resize(
            (math.ceil(source.width * scale), math.ceil(source.height * scale)),
            Image.Resampling.LANCZOS,
        )
        left = (resized.width - width) // 2
        top = (resized.height - height) // 2
        frame = resized.crop((left, top, left + width, top + height))
        frame.save(output_path, format="PNG", compress_level=2)
