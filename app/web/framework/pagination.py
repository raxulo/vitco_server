"""
Page links shared by every list: First, Previous, a few numbers around the current page, Next, Last.

Python 3.13+
"""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import Request

_NUMBERS_SHOWN = 5


def page_numbers(page: int, total_pages: int, shown: int = _NUMBERS_SHOWN) -> list[int]:
    """
    The current page in the middle, two either side: page 10 of 20 gives 8 to 12.

    Near the ends the window slides so the same count stays visible: page 1 gives 1 to 5.
    """
    if total_pages <= 0:
        return []
    page = min(max(page, 1), total_pages)
    first = max(1, min(page - shown // 2, total_pages - shown + 1))
    last = min(total_pages, first + shown - 1)
    return list(range(first, last + 1))


def page_url(request: Request, number: int) -> str:
    """The current page's address with only `page` changed, so every search and filter is kept."""
    params = [(key, value) for key, value in request.query_params.multi_items() if key != "page"]
    params.append(("page", str(number)))
    return f"{request.url.path}?{urlencode(params)}"
