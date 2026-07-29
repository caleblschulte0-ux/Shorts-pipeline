"""MOVED to funnel/topic_video.py (pipeline reorg 2026-07-30 — docs/PIPELINE_LAYOUT.md).

Compatibility shim: keeps every legacy `import topic_video` working and pointing at
the SAME module object as `funnel.topic_video` (caches/quota/singletons stay shared).
New code imports from funnel.topic_video directly.
"""
import sys as _sys
from funnel import topic_video as _impl
_sys.modules[__name__] = _impl
