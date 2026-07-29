"""shared/ — CROSS-CHANNEL UTILITIES (pipeline reorg, see docs/PIPELINE_LAYOUT.md).

Anything every channel needs that is not media acquisition (funnel/) or a
registered render engine (engines/): atomic state IO, the multi-channel
YouTube uploader/token router, translation, the LLM call helpers, and the
themed bottom-half game renderer.

Keep this __init__ import-free — see funnel/__init__.py for why.
"""
