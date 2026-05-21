"""Standalone LaMa inpainting worker — runs in the lama_env conda environment.

Usage:
    python lama_inpaint_worker.py <image_path> <mask_path> <output_path>
"""
import sys

if len(sys.argv) != 4:
    print("Usage: lama_inpaint_worker.py <image> <mask> <output>", file=sys.stderr)
    sys.exit(1)

image_path, mask_path, output_path = sys.argv[1], sys.argv[2], sys.argv[3]

from simple_lama_inpainting import SimpleLama
from PIL import Image

lama = SimpleLama()
image = Image.open(image_path).convert("RGB")
mask = Image.open(mask_path).convert("L")
result = lama(image, mask)
result.save(output_path)
print("done")
