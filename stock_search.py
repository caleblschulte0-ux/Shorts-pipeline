"""MOVED to funnel/stock_search.py (pipeline reorg 2026-07-30 — docs/PIPELINE_LAYOUT.md).

Compatibility shim: keeps every legacy `import stock_search` working and pointing at
the SAME module object as `funnel.stock_search` (caches/quota/singletons stay shared).
New code imports from funnel.stock_search directly.
"""
import sys as _sys
from funnel import stock_search as _impl
_sys.modules[__name__] = _impl
