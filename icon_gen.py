"""Generates icon.ico in the project directory using Pillow."""
import os
import sys
from PIL import Image, ImageDraw

if getattr(sys, 'frozen', False):
    _exe_dir = os.path.dirname(sys.executable)
    SCRIPT_DIR = os.path.dirname(_exe_dir) if not os.path.exists(
        os.path.join(_exe_dir, 'config.py')) else _exe_dir
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(SCRIPT_DIR, "icon.ico")

def create_icon():
    """Draw a microphone icon and save as multi-res .ico."""
    sizes = [16, 32, 48]
    images = []
    for size in sizes:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        s = size
        bx = int(s * 0.33)
        bw = int(s * 0.34)
        bt = int(s * 0.08)
        bb = int(s * 0.58)
        draw.rounded_rectangle([bx, bt, bx + bw, bb], radius=int(bw * 0.5), fill=(220, 220, 220, 255))
        ax = int(s * 0.18)
        aw = int(s * 0.64)
        at = int(s * 0.48)
        ab = int(s * 0.80)
        draw.arc([ax, at, ax + aw, ab], start=0, end=180, fill=(180, 180, 180, 255), width=max(1, int(s * 0.07)))
        cx = s // 2
        draw.line([(cx, int(s * 0.78)), (cx, int(s * 0.90))], fill=(180, 180, 180, 255), width=max(1, int(s * 0.06)))
        bsx = int(s * 0.28)
        bex = int(s * 0.72)
        by2 = int(s * 0.90)
        draw.line([(bsx, by2), (bex, by2)], fill=(180, 180, 180, 255), width=max(1, int(s * 0.06)))
        images.append(img)
    images[0].save(ICON_PATH, format="ICO", sizes=[(s, s) for s in sizes], append_images=images[1:])
    return ICON_PATH

if __name__ == "__main__":
    path = create_icon()
    print(f"Icon written to {path}")
