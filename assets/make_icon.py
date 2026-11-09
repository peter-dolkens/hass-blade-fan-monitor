"""Integration icon: a big F in the Compute Blade wordmark style.

Lime #CCFF3D square with a black glyph, like the Compute Blade favicon. The F is
the wordmark's E without its bottom bar or chamfer, with the top arm shortened
to match the detached stencil mid-bar. Coordinates are in blade-logo.svg units
(cap height 14.03 -> 42.76; slanted ends run dx/dy = -0.68).

Regenerate:  python3 assets/make_icon.py && assets/render.sh
"""

import os

LIME, INK = "#CCFF3D", "#000000"
S = 512
FILL = 0.60  # glyph's longer side as a fraction of the square, as in the favicon

F = [
    # Square-cornered stem and the top arm.
    [(115.57, 21.209), (132.806, 21.216), (137.7, 14.032), (107.81, 14.032),
     (107.804, 42.762), (115.577, 42.762)],
    # Mid arm: a separate parallelogram, slanted at both ends, same length as the top.
    [(137.7, 24.569), (132.806, 31.753), (115.57, 31.753), (120.451, 24.596)],
]


def svg(polys):
    xs = [x for p in polys for x, _ in p]
    ys = [y for p in polys for _, y in p]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    k = S * FILL / max(w, h)
    ox = (S - w * k) / 2 - min(xs) * k
    oy = (S - h * k) / 2 - min(ys) * k
    paths = "".join(
        '<path d="M'
        + " L".join(f"{x * k + ox:.1f} {y * k + oy:.1f}" for x, y in p)
        + f' Z" fill="{INK}"/>'
        for p in polys
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S} {S}" width="{S}" height="{S}">'
        f'<rect width="{S}" height="{S}" fill="{LIME}"/>{paths}</svg>\n'
    )


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.svg")
    with open(out, "w") as f:
        f.write(svg(F))
