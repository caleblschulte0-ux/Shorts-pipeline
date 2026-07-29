"""MOVED to shared/localize.py (pipeline reorg 2026-07-30 — docs/PIPELINE_LAYOUT.md).

Compatibility shim: keeps every legacy `import localize` working and pointing at
the SAME module object as `shared.localize`. New code imports from shared.localize.
"""
import sys as _sys
from shared import localize as _impl
_sys.modules[__name__] = _impl
