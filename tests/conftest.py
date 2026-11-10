"""Shared pytest configuration."""

# Browser tests (tests/e2e) need the e2e extra and a Chromium; leave them out when it isn't installed.
try:
    import playwright.sync_api  # noqa: F401
except Exception:
    collect_ignore = ["e2e"]
