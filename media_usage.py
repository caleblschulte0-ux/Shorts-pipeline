"""MOVED to funnel/media_usage.py (pipeline reorg 2026-07-30 — docs/PIPELINE_LAYOUT.md).

Compatibility shim: keeps every legacy `import media_usage` working and pointing at
the SAME module object as `funnel.media_usage` (caches/quota/singletons stay shared).
New code imports from funnel.media_usage directly.
"""
import sys as _sys
from funnel import media_usage as _impl
_sys.modules[__name__] = _impl
