from __future__ import annotations

import json
from starlette.responses import Response

from enum import StrEnum

class HTMXEvent(StrEnum):
    NOTIFICATION = "notification"
    CLOSE_MODAL = "close-modal"
    REFRESH_TABLE = "refresh-table"
    REFRESH_USER_COUNT = "refresh-user-count"

import json
from starlette.responses import Response

class HTMXBuilder:

    def __init__(self, response: Response):
        self.response = response
        self.events = {}

    # -----------------------------
    # Generic Event
    # -----------------------------

    def trigger(self, event: HTMXEvent, data=None):
        self.events[event] = data or {}
        return self

    # -----------------------------
    # Notification
    # -----------------------------

    def success(self, message):
        return self.trigger(
            HTMXEvent.NOTIFICATION,
            {
                "type": "success",
                "title": "Success",
                "message": message,
            },
        )

    def error(self, message):
        return self.trigger(
            HTMXEvent.NOTIFICATION,
            {
                "type": "error",
                "title": "Error",
                "message": message,
            },
        )

    def warning(self, message):
        return self.trigger(
            HTMXEvent.NOTIFICATION,
            {
                "type": "warning",
                "title": "Warning",
                "message": message,
            },
        )

    def info(self, message):
        return self.trigger(
            HTMXEvent.NOTIFICATION,
            {
                "type": "info",
                "title": "Information",
                "message": message,
            },
        )

    # -----------------------------
    # Redirect
    # -----------------------------

    def redirect(self, url, delay=0):
        return self.trigger(
            HTMXEvent.REDIRECT,

            {
                "url": url,
                "delay": delay,
            }

        )

    # -----------------------------
    # Helpers
    # -----------------------------

    def close_modal(self):

        return self.trigger(
            HTMXEvent.CLOSE_MODAL
        )

    def refresh_table(self):
        return self.trigger(
            HTMXEvent.REFRESH_TABLE
        )

    def refresh_user_count(self):
        return self.trigger(
            HTMXEvent.REFRESH_USER_COUNT
        )

    def refresh_page(self):

        return self.trigger(
            HTMXEvent.REFRESH_PAGE
        )

    # -----------------------------
    # Build
    # -----------------------------

    def build(self):
        if self.events:
            self.response.headers["HX-Trigger"] = json.dumps(self.events)
        return self.response