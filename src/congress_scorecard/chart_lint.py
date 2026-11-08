"""Automated geometry checks for exported project charts."""
from pathlib import Path

from matplotlib.text import Text
from PIL import Image

from .plotting import font_properties


def lint_chart(canvas, png):
    """Return failures for image dimensions, text bounds, and text collisions."""
    failures = []
    try:
        with Image.open(png) as image:
            if image.format != "PNG":
                failures.append("Export must be a PNG image.")
            if image.size != (canvas.W, canvas.H):
                failures.append("Export dimensions differ from the selected canvas.")
    except (OSError, ValueError) as error:
        failures.append(f"Export is unreadable: {type(error).__name__}.")
    canvas.fig.canvas.draw()
    renderer = canvas.fig.canvas.get_renderer()
    margin_x = canvas.W * .05
    margin_y = canvas.H * (.12 if (canvas.W, canvas.H) == (1080, 1920) else .05)
    boxes = []
    allowed_fonts = {font_properties(role).get_name() for role in ("body", "headline", "emphasis")}
    from matplotlib import get_data_path
    symbol_font = (Path(get_data_path()) / "fonts/ttf/DejaVuSans.ttf").resolve()
    for artist in canvas.fig.findobj(match=Text):
        text = artist.get_text().strip()
        if not text or not artist.get_visible():
            continue
        font_file = artist.get_fontproperties().get_file()
        approved_symbol = text == "ρ" and font_file and Path(font_file).resolve() == symbol_font
        if artist.get_fontproperties().get_name() not in allowed_fonts and not approved_symbol:
            failures.append(f"Unexpected font family: {text!r}.")
        box = artist.get_window_extent(renderer)
        if (box.x0 < margin_x - 2 or box.x1 > canvas.W - margin_x + 2
                or box.y0 < margin_y - 2 or box.y1 > canvas.H - margin_y + 2):
            failures.append(f"Text extends beyond the safe area: {text!r}.")
        if any(box.overlaps(other) for _, other in boxes):
            failures.append(f"Text overlaps another label: {text!r}.")
        boxes.append((text, box))
    logo_axes = [axes for axes in canvas.fig.axes if axes.images]
    for axes in logo_axes:
        logo_box = axes.get_window_extent(renderer)
        logo_box = logo_box.padded(logo_box.height * .206)
        for text, box in boxes:
            if box.overlaps(logo_box):
                failures.append(f"Text overlaps the logo: {text!r}.")
    return {
        "passed": not failures,
        "checks": ["PNG readability", "image dimensions", "text safe areas",
                   "text collisions", "font families", "logo clear space"],
        "failures": failures,
        "image": Path(png).name,
        "dimensions": [canvas.W, canvas.H],
        "text_labels_checked": len(boxes),
    }
