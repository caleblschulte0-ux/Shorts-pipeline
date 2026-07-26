"""Sprint 10 launch-closure package.

This package rehearses production-shaped migration behavior without importing,
modifying, publishing through, or writing into the live pipeline.
"""

from .closure import build_launch_report, run_launch_rehearsal

__all__ = ["build_launch_report", "run_launch_rehearsal"]
