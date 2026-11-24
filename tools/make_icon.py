"""Generate the application icon (app.ico).

    python tools/make_icon.py

Draws a squircle with a document and a signature stroke, then writes a
multi-resolution .ico for the Windows title bar and taskbar.
"""
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "app.ico")
SIZES = (16, 24, 32, 48, 64, 128, 256)


def draw_icon(size: int) -> Image.Image:
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # squircle background with a soft vertical gradient
    grad = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(s):
        t = y / max(1, s - 1)
        color = (int(0 + 26 * t), int(122 - 40 * t), int(255 - 10 * t), 255)
        gd.line([(0, y), (s, y)], fill=color)
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, s - 1, s - 1],
                                           radius=int(s * 0.225), fill=255)
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)

    # white page
    m = s * 0.26
    page = [m, s * 0.20, s - m, s * 0.80]
    d.rounded_rectangle(page, radius=int(s * 0.035), fill=(255, 255, 255, 255))

    # folded corner
    fold = s * 0.12
    d.polygon([(s - m - fold, s * 0.20), (s - m, s * 0.20),
               (s - m, s * 0.20 + fold)], fill=(214, 226, 245, 255))

    # signature stroke
    w = max(1, int(s * 0.035))
    pts = [(s * 0.34, s * 0.60), (s * 0.42, s * 0.42), (s * 0.50, s * 0.62),
           (s * 0.58, s * 0.44), (s * 0.68, s * 0.62)]
    d.line(pts, fill=(0, 90, 220, 255), width=w, joint="curve")
    d.line([(s * 0.33, s * 0.68), (s * 0.70, s * 0.68)],
           fill=(0, 90, 220, 255), width=max(1, int(s * 0.025)))
    return img


def main() -> None:
    frames = [draw_icon(s) for s in SIZES]
    frames[0].save(OUT, format="ICO",
                   sizes=[(s, s) for s in SIZES],
                   append_images=frames[1:])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
