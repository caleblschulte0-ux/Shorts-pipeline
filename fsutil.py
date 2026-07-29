"""MOVED to shared/fsutil.py (pipeline reorg 2026-07-30 — docs/PIPELINE_LAYOUT.md).

Compatibility shim: keeps every legacy `import fsutil` working and pointing at
the SAME module object as `shared.fsutil`. New code imports from shared.fsutil.
"""
import sys as _sys
from shared import fsutil as _impl
_sys.modules[__name__] = _impl
