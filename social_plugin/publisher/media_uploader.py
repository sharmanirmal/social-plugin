"""Image/video validation and resize for social media posting."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from social_plugin.utils.logger import get_logger

logger = get_logger()

# Twitter image limits
TWITTER_MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
TWITTER_MAX_DIMENSIONS = (4096, 4096)
TWITTER_SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

# LinkedIn image limits
LINKEDIN_MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
LINKEDIN_SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".gif"}


def validate_image(image_path: str, platform: str = "twitter") -> bool:
    """Validate an image for a specific platform."""
    path = Path(image_path)
    if not path.exists():
        logger.warning("Image not found: %s", path)
        return False

    suffix = path.suffix.lower()
    if platform == "twitter":
        supported = TWITTER_SUPPORTED_FORMATS
        max_size = TWITTER_MAX_IMAGE_SIZE
    else:
        supported = LINKEDIN_SUPPORTED_FORMATS
        max_size = LINKEDIN_MAX_IMAGE_SIZE

    if suffix not in supported:
        logger.warning("Unsupported image format %s for %s", suffix, platform)
        return False

    file_size = path.stat().st_size
    if file_size > max_size:
        logger.warning("Image too large: %d bytes (max %d)", file_size, max_size)
        return False

    return True


def resize_image(image_path: str, max_width: int = 2048, max_height: int = 2048, output_path: str | None = None) -> str:
    """Resize an image to fit within max dimensions."""
    path = Path(image_path)
    output = Path(output_path) if output_path else path.with_stem(f"{path.stem}_resized")

    with Image.open(path) as img:
        if img.width <= max_width and img.height <= max_height:
            logger.info("Image already within bounds: %dx%d", img.width, img.height)
            return str(path)

        img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        img.save(str(output), quality=90)
        logger.info("Resized image to %dx%d -> %s", img.width, img.height, output)

    return str(output)
