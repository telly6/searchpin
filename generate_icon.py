#!/usr/bin/env python3
"""Generate MiniSearch icon (.icns for macOS). Requires Pillow."""
import struct
import os
from PIL import Image, ImageDraw

OUTPUT = os.path.join(os.path.dirname(__file__), "MiniSearch.icns")

SIZES = [16, 32, 64, 128, 256, 512]


def draw_icon(size):
    """Draw a magnifying glass icon at given size."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Glass circle
    circle_r = int(size * 0.35)
    circle_x = int(size * 0.38)
    circle_y = int(size * 0.32)
    line_w = max(2, int(size * 0.08))

    # Handle line (diagonal)
    start_x = int(size * 0.62)
    start_y = int(size * 0.58)
    end_x = int(size * 0.82)
    end_y = int(size * 0.80)

    # Draw handle
    draw.line(
        [(start_x, start_y), (end_x, end_y)],
        fill=(100, 100, 100, 255),
        width=line_w,
    )

    # Draw circle outline
    draw.ellipse(
        [
            circle_x - circle_r,
            circle_y - circle_r,
            circle_x + circle_r,
            circle_y + circle_r,
        ],
        outline=(100, 100, 100, 255),
        width=line_w,
    )

    return img


def build_iconset():
    """Build .iconset directory and return path."""
    iconset = os.path.join(os.path.dirname(__file__), "MiniSearch.iconset")
    os.makedirs(iconset, exist_ok=True)

    for s in SIZES:
        img = draw_icon(s)
        img.save(os.path.join(iconset, f"icon_{s}x{s}.png"))
        # Retina
        s2 = s * 2
        img2 = draw_icon(s2)
        img2.save(os.path.join(iconset, f"icon_{s}x{s}@2x.png"))

    return iconset


def iconset_to_icns(iconset_dir, output_path):
    """Use macOS iconutil to convert iconset to .icns."""
    import subprocess
    subprocess.run(["iconutil", "-c", "icns", iconset_dir, "-o", output_path], check=True)

    # Cleanup
    import shutil
    shutil.rmtree(iconset_dir)


if __name__ == "__main__":
    print(f"[IconGen] generating iconset ...")
    iconset = build_iconset()
    print(f"[IconGen] converting to .icns ...")
    iconset_to_icns(iconset, OUTPUT)
    print(f"[IconGen] done → {OUTPUT}")
