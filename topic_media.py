"""MOVED to funnel/topic_media.py (pipeline reorg 2026-07-30 — docs/PIPELINE_LAYOUT.md).

Compatibility shim: keeps every legacy `import topic_media` working and pointing at
the SAME module object as `funnel.topic_media` (caches/quota/singletons stay shared).
New code imports from funnel.topic_media directly.
"""
import sys as _sys
from funnel import topic_media as _impl
_sys.modules[__name__] = _impl
