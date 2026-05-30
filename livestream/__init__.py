"""Livestream module — weekly themed background-loop generator.

Fully isolated from the main app: own entry point (build_loop.py), own trigger
(.github/workflows/livestream.yml), own output dir (outbox/). It imports from
shared/ but never touches make_short.py, the daily orchestrator, state/, the
catalog, or the PAUSED kill switch. A crash here cannot affect the money-maker.
"""
