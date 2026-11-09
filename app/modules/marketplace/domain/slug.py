"""
URL slugs for listings and categories.

Python 3.13+
"""

import re
import unicodedata
from uuid import uuid4

_NOT_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_length: int = 180) -> str:
    """Lowercase ASCII words joined by hyphens; text without Latin letters gets a short random id."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = _NOT_SLUG.sub("-", ascii_text.lower()).strip("-")[:max_length].rstrip("-")
    return slug or f"item-{uuid4().hex[:8]}"
