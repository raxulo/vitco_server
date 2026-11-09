"""
Links typed in the Control Center render as links for every customer, so only site
paths and http(s) URLs are accepted. This blocks javascript: and data: links.

Python 3.13+
"""

from urllib.parse import urlsplit


def is_safe_link(url: str) -> bool:
    value = url.strip()
    if not value or any(ord(char) < 33 for char in value) or "\\" in value:
        return False
    if value.startswith("/"):
        return not value.startswith("//")
    try:
        parts = urlsplit(value)
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.netloc)
