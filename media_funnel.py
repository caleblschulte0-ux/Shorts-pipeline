"""MOVED to funnel/media_funnel.py (pipeline reorg 2026-07-30 — docs/PIPELINE_LAYOUT.md).

Compatibility shim: keeps every legacy `import media_funnel` working and pointing at
the SAME module object as `funnel.media_funnel` (caches/quota/singletons stay shared).
New code imports from funnel.media_funnel directly.
"""
import sys as _sys
from funnel import media_funnel as _impl
_sys.modules[__name__] = _impl
