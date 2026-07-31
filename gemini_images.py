"""MOVED to funnel/gemini_images.py (pipeline reorg 2026-07-30 — docs/PIPELINE_LAYOUT.md).

Compatibility shim: keeps every legacy `import gemini_images` working and pointing at
the SAME module object as `funnel.gemini_images` (caches/quota/singletons stay shared).
New code imports from funnel.gemini_images directly.
"""
import sys as _sys
from funnel import gemini_images as _impl
_sys.modules[__name__] = _impl
