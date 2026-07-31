"""MOVED to shared/themed_bottom.py (pipeline reorg 2026-07-30 — docs/PIPELINE_LAYOUT.md).

Compatibility shim: keeps every legacy `import themed_bottom` working and pointing at
the SAME module object as `shared.themed_bottom`. New code imports from shared.themed_bottom.
"""
import sys as _sys
from shared import themed_bottom as _impl
_sys.modules[__name__] = _impl
