#!/usr/bin/env python3
"""Draw the generic outfield background used behind the spray chart.

The spray dots and fielder markers are placed by pixel calibration
(SPRAY_PIXEL_CONFIG in app.py: home plate, the two foul poles, and the
fence-to-infield band). This image is drawn to those same pixels, so the dots
land on the right part of the field. If you change SPRAY_PIXEL_CONFIG, change
the numbers below to match and re-run:

    python scripts/make_generic_background.py

No real ballpark, logo, or team branding appears in the image.
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# Keep in sync with SPRAY_PIXEL_CONFIG in app.py.
W, H = 2340, 1560
HOME = (1170, 1600)
LF_POLE = (248, 848)
RF_POLE = (2114, 854)
FENCE_TOP_CENTER_Y = 716          # fence line at straightaway center
S = 2                             # supersample for smooth edges

# Bases. Home plate sits below the bottom of the image (see HOME), so only first,
# second and third are drawn. Rows are picked so 1B and 3B sit on the foul lines
# and 2B on the center line, in the same perspective the spray dots use. Set
# DRAW_BASES = False for a plain outfield with no infield markings.
DRAW_BASES = True
BASE_CORNER_Y = 1285              # row of first and third base
BASE_SECOND_Y = 1030              # row of second base


def lerp(a, b, t):
    return a + (b - a) * t


def fence_y(x):
    """Fence line: through both poles and the center point (a smooth arc)."""
    # Quadratic through (LF_POLE), (home_x, center), (RF_POLE).
    x0, y0 = LF_POLE
    x1, y1 = HOME[0], FENCE_TOP_CENTER_Y
    x2, y2 = RF_POLE
    l0 = (x - x1) * (x - x2) / ((x0 - x1) * (x0 - x2))
    l1 = (x - x0) * (x - x2) / ((x1 - x0) * (x1 - x2))
    l2 = (x - x0) * (x - x1) / ((x2 - x0) * (x2 - x1))
    return y0 * l0 + y1 * l1 + y2 * l2


def foul_x(y, pole):
    """x of the foul line from home plate through ``pole`` at row ``y``."""
    return HOME[0] + (y - HOME[1]) * (pole[0] - HOME[0]) / (pole[1] - HOME[1])


def main(out_path):
    w, h = W * S, H * S
    img = Image.new("RGB", (w, h))
    px = np.zeros((h, w, 3), dtype=np.float32)

    # Sky and stands above the fence, as a vertical gradient.
    ys = np.arange(h, dtype=np.float32)[:, None] / S
    sky = np.array([[120, 170, 215]], dtype=np.float32)
    dusk = np.array([[225, 190, 160]], dtype=np.float32)
    t = np.clip(ys / 420.0, 0, 1)
    px[:] = (sky * (1 - t) + dusk * t)[:, None, :]
    img = Image.fromarray(px.astype(np.uint8))
    d = ImageDraw.Draw(img)

    def P(x, y):
        return (x * S, y * S)

    # Grandstand band, darker bluish-grey with faint seat rows.
    xs = list(range(0, W + 1, 20))
    stand_top = [(x, fence_y(x) - 330 + 0.18 * abs(x - HOME[0]) * 0) for x in xs]
    d.polygon([P(x, y) for x, y in stand_top] + [P(W, H), P(0, H)], fill=(58, 66, 92))
    for k in range(14):
        off = 30 + k * 22
        d.line([P(x, fence_y(x) - off) for x in xs], fill=(70 + k * 2, 78 + k * 2, 108 + k * 2),
               width=int(7 * S))

    # Outfield wall: dark green padding with a pale cap line.
    wall_h = 56
    d.polygon([P(x, fence_y(x) - wall_h) for x in xs] + [P(x, fence_y(x)) for x in reversed(xs)],
              fill=(20, 72, 52))
    d.line([P(x, fence_y(x) - wall_h) for x in xs], fill=(235, 220, 90), width=int(6 * S))

    # Warning track: a dirt band just inside the wall, following the fence.
    track = 46
    d.polygon([P(x, fence_y(x)) for x in xs] + [P(x, fence_y(x) + track) for x in reversed(xs)],
              fill=(168, 120, 78))

    # Grass: everything below the warning track, with mowing arcs around home.
    grass = Image.new("RGB", (w, h), (46, 128, 66))
    gd = ImageDraw.Draw(grass)
    r_max = int(math.hypot(HOME[0], HOME[1])) + 400
    band = 70
    for i, r in enumerate(range(r_max, 0, -band)):
        # Subtle mowing stripes, and none near home plate so no infield look.
        light = (r // band) % 2 == 0 and r > 700
        shade = (50, 134, 68) if light else (46, 128, 66)
        gd.ellipse([P(HOME[0] - r, HOME[1] - r), P(HOME[0] + r, HOME[1] + r)], fill=shade)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).polygon(
        [P(x, fence_y(x) + track) for x in xs] + [P(W, H), P(0, H)], fill=255)
    img.paste(grass, (0, 0), mask)
    d = ImageDraw.Draw(img)

    # Foul lines from the poles down toward home plate, plus the pole itself.
    for pole in (LF_POLE, RF_POLE):
        y_top = fence_y(pole[0]) + track
        d.line([P(foul_x(y_top, pole), y_top), P(foul_x(H, pole), H)],
               fill=(250, 250, 250), width=int(7 * S))
        d.line([P(pole[0], pole[1] - 190), P(pole[0], pole[1] + 6)],
               fill=(245, 205, 40), width=int(10 * S))

    if DRAW_BASES:
        bases = [(foul_x(BASE_CORNER_Y, LF_POLE), BASE_CORNER_Y),
                 (HOME[0], BASE_SECOND_Y),
                 (foul_x(BASE_CORNER_Y, RF_POLE), BASE_CORNER_Y)]
        first, second, third = bases   # left base, second, right base
        dirt = (176, 128, 84)
        path_hw = 23                   # half width of a base path, in pixels

        def strip(a, b):
            """Filled strip centered exactly on the segment a-b."""
            dx, dy = b[0] - a[0], b[1] - a[1]
            n = math.hypot(dx, dy)
            ox, oy = -dy / n * path_hw, dx / n * path_hw
            return [P(a[0] + ox, a[1] + oy), P(b[0] + ox, b[1] + oy),
                    P(b[0] - ox, b[1] - oy), P(a[0] - ox, a[1] - oy)]

        d.polygon(strip(first, second), fill=dirt)
        d.polygon(strip(second, third), fill=dirt)
        for base, pole in ((first, LF_POLE), (third, RF_POLE)):   # lines run toward home
            d.polygon(strip(base, (foul_x(H, pole), H)), fill=dirt)
        for bx, by in bases:           # dirt patch under each base
            d.ellipse([P(bx - 78, by - 44), P(bx + 78, by + 44)], fill=(176, 128, 84))
        for pole in (LF_POLE, RF_POLE):  # redraw the foul line over the dirt
            y_top = BASE_CORNER_Y - 80
            d.line([P(foul_x(y_top, pole), y_top), P(foul_x(H, pole), H)],
                   fill=(250, 250, 250), width=int(7 * S))
        for bx, by in bases:           # the bag itself, a flattened diamond
            d.polygon([P(bx, by - 15), P(bx + 26, by), P(bx, by + 15), P(bx - 26, by)],
                      fill=(255, 255, 255), outline=(200, 200, 200))

    img = img.resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.6))
    img.save(out_path, optimize=True)
    print(f"wrote {out_path} ({W}x{H})")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "img/background_generic.png"))
