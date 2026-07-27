#!/usr/bin/env bash
set -euo pipefail

# REVIEW-ONLY INSTALLER. This file is not called by any workflow.
# Claude should copy exact, reviewed pieces into a versioned runner image later.

sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  ffmpeg imagemagick libreoffice graphviz blender \
  tesseract-ocr poppler-utils rubberband-cli audacity \
  libcairo2-dev libpango1.0-dev pkg-config python3-dev python3-venv \
  texlive-latex-base texlive-latex-extra dvisvgm

python -m pip install --upgrade pip
python -m pip install -r review_prototypes/capability_studio/toolchain/requirements-core.txt
python -m pip install manim demucs rembg mediapipe transformers torch
npm install --prefix review_prototypes/capability_studio/toolchain

# Deliberately omitted:
# - SAM 2 checkpoint download (must be release/license/hash pinned)
# - paid APIs
# - production workflow edits
