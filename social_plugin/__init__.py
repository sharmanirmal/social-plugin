"""Social Plugin — AI-powered social media content generation and publishing."""

try:
    from importlib.metadata import version

    __version__ = version("social-plugin")
except Exception:
    __version__ = "0.1.0"
