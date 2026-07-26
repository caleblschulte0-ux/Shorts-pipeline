"""Deterministic visible-quality preview lab.

Review-only. It emits SVG keyframes, storyboards, timing manifests, and quality
reports without importing or altering the production renderer.
"""

from .preview_compiler import compile_preview, write_preview_bundle
from .quality_linter import lint_preview

__all__ = ["compile_preview", "write_preview_bundle", "lint_preview"]
