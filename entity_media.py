"""MOVED to funnel/entity_media.py (pipeline reorg 2026-07-30 — docs/PIPELINE_LAYOUT.md).

Compatibility shim: keeps every legacy `import entity_media` working and pointing at
the SAME module object as `funnel.entity_media` (caches/quota/singletons stay shared).
New code imports from funnel.entity_media directly.
"""
import sys as _sys
from funnel import entity_media as _impl
_sys.modules[__name__] = _impl
