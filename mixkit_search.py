"""MOVED to funnel/mixkit_search.py (pipeline reorg 2026-07-30 — docs/PIPELINE_LAYOUT.md).

Compatibility shim: keeps every legacy `import mixkit_search` working and pointing at
the SAME module object as `funnel.mixkit_search` (caches/quota/singletons stay shared).
New code imports from funnel.mixkit_search directly.
"""
import sys as _sys
from funnel import mixkit_search as _impl
_sys.modules[__name__] = _impl
