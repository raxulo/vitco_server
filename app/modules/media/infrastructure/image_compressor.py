"""
Image processing for uploaded profile images (Python 3.13+).

Every upload is decoded and re-encoded (never stored as received), which:
- proves the bytes really are an image (the client's content-type is not trusted),
- strips EXIF metadata such as the GPS location of a phone photo,
- rejects decompression bombs (absurd pixel counts).

A single WebP image is produced: longest side <= 1024 px and at most 100 KB
(quality is lowered first, then the dimensions).
"""

from io import BytesIO

from PIL import Image, ImageOps

PROFILE_IMAGE_MAX_BYTES = 100 * 1024

_MAX_SIDE = 1024
_QUALITY_STEPS = (85, 75, 65, 55, 45, 35)
_SCALE_STEP = 0.8
_MIN_SIDE = 64
_MAX_PIXELS = 40_000_000  # ~40 MP; anything larger is refused

MIME_TYPE = "image/webp"
EXTENSION = ".webp"


class ProcessedImage:
    __slots__ = ("data", "mime_type", "extension")

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.mime_type = MIME_TYPE
        self.extension = EXTENSION


class ImageProcessor:
    __slots__ = ("_max_bytes", "_max_side",)

    def __init__(self, max_bytes: int = PROFILE_IMAGE_MAX_BYTES, max_side: int = _MAX_SIDE) -> None:
        self._max_bytes = max_bytes
        self._max_side = max_side

    def process(self, data: bytes) -> ProcessedImage:
        image = self._fit(self._open(data), self._max_side)
        return ProcessedImage(self._encode_within_limit(image))

    # -----------------------------------------------------

    @staticmethod
    def _open(data: bytes) -> Image.Image:
        try:
            probe = Image.open(BytesIO(data))
            width, height = probe.size
            if width * height > _MAX_PIXELS:
                raise ValueError("Image dimensions are too large")
            probe.load()
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("Invalid image file") from exc

        # Apply camera rotation; the EXIF block itself is not carried over
        image = ImageOps.exif_transpose(probe)
        has_alpha = image.mode in ("RGBA", "LA", "PA") or (image.mode == "P" and "transparency" in image.info)
        return image.convert("RGBA" if has_alpha else "RGB")

    @staticmethod
    def _fit(image: Image.Image, max_side: int) -> Image.Image:
        fitted = image.copy()
        fitted.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        return fitted

    def _encode_within_limit(self, image: Image.Image) -> bytes:
        while True:
            for quality in _QUALITY_STEPS:
                encoded = self._encode(image, quality)
                if len(encoded) <= self._max_bytes:
                    return encoded

            width, height = image.size
            if min(width, height) <= _MIN_SIDE:
                # Smallest sensible size reached; keep the smallest encoding
                return encoded
            image = image.resize(
                (max(1, int(width * _SCALE_STEP)), max(1, int(height * _SCALE_STEP))),
                Image.Resampling.LANCZOS,
            )

    @staticmethod
    def _encode(image: Image.Image, quality: int) -> bytes:
        buffer = BytesIO()
        # No exif= argument: metadata is dropped from the output
        image.save(buffer, format="WEBP", quality=quality, method=6)
        return buffer.getvalue()
