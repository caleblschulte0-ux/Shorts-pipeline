"""MOVED to funnel/higgsfield.py (pipeline reorg 2026-07-30 — docs/PIPELINE_LAYOUT.md).

Compatibility shim: keeps every legacy `import higgsfield` working and pointing at
the SAME module object as `funnel.higgsfield` (caches/quota/singletons stay shared).
New code imports from funnel.higgsfield directly.
"""
import sys as _sys
from funnel import higgsfield as _impl
_sys.modules[__name__] = _impl
