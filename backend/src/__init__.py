"""Backend package exports.

Keep imports side-effect free at package import time.
"""

__all__ = ["get_app"]


def get_app():
    from .index import app

    return app
