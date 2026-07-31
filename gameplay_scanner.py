"""MOVED to funnel/gameplay_scanner.py (pipeline reorg 2026-07-30 — docs/PIPELINE_LAYOUT.md).

Compatibility shim: keeps every legacy `import gameplay_scanner` working and pointing at
the SAME module object as `funnel.gameplay_scanner` (caches/quota/singletons stay shared).
New code imports from funnel.gameplay_scanner directly.
"""
import sys as _sys
from funnel import gameplay_scanner as _impl
_sys.modules[__name__] = _impl
