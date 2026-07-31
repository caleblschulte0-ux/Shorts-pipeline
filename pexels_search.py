"""MOVED to funnel/pexels_search.py (pipeline reorg 2026-07-30 — docs/PIPELINE_LAYOUT.md).

Compatibility shim: keeps every legacy `import pexels_search` working and pointing at
the SAME module object as `funnel.pexels_search` (caches/quota/singletons stay shared).
New code imports from funnel.pexels_search directly.
"""
import sys as _sys
from funnel import pexels_search as _impl
_sys.modules[__name__] = _impl
