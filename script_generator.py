"""MOVED to shared/script_generator.py (pipeline reorg 2026-07-30 — docs/PIPELINE_LAYOUT.md).

Compatibility shim: keeps every legacy `import script_generator` working and pointing at
the SAME module object as `shared.script_generator`. New code imports from shared.script_generator.
"""
import sys as _sys
from shared import script_generator as _impl
_sys.modules[__name__] = _impl
