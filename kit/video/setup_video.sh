#!/usr/bin/env bash
# One-time setup for kit/video/engine.py: Python packages + Kokoro-82M voice model (~170 MB, Apache-2.0).
# Model goes to $KOKORO_DIR (default ~/.cache/kokoro). Safe to re-run.
set -euo pipefail
KDIR="${KOKORO_DIR:-$HOME/.cache/kokoro}"
FLAGS=(); [ -n "${VIRTUAL_ENV:-}" ] || FLAGS=(--user --break-system-packages)   # outside a venv: user site
python3 -c 'import matplotlib, PIL, imageio_ffmpeg, soundfile, kokoro_onnx' 2>/dev/null ||
  python3 -m pip install "${FLAGS[@]}" -q matplotlib pillow imageio-ffmpeg soundfile kokoro-onnx
mkdir -p "$KDIR"
for f in kokoro-v1.0.fp16.onnx voices-v1.0.bin; do
  [ -s "$KDIR/$f" ] || curl -fL --retry 3 -o "$KDIR/$f" \
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/$f"
done
ls -la "$KDIR"
echo "ready: KOKORO_DIR=$KDIR"
