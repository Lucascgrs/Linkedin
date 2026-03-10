"""
Backward-compatibility shim — StealthBrowser is now part of the linkedin package.
Prefer importing from linkedin.utils.stealth_browser or from linkedin directly.
"""
from linkedin.utils.stealth_browser import StealthBrowser, SESSION_FILE  # noqa: F401

__all__ = ["StealthBrowser", "SESSION_FILE"]
