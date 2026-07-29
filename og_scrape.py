"""MOVED to funnel/og_scrape.py (pipeline reorg 2026-07-30 — docs/PIPELINE_LAYOUT.md).

Compatibility shim: keeps every legacy `import og_scrape` working and pointing at
the SAME module object as `funnel.og_scrape` (caches/quota/singletons stay shared).
New code imports from funnel.og_scrape directly.
"""
import sys as _sys
from funnel import og_scrape as _impl
_sys.modules[__name__] = _impl
