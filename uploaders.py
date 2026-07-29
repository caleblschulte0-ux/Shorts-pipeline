"""MOVED to shared/uploaders.py (pipeline reorg 2026-07-30 — docs/PIPELINE_LAYOUT.md).

Compatibility shim: keeps every legacy `import uploaders` working and pointing at
the SAME module object as `shared.uploaders`. New code imports from shared.uploaders.
"""
import sys as _sys
from shared import uploaders as _impl
_sys.modules[__name__] = _impl
