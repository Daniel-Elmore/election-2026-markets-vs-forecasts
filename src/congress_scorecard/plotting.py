"""Chart styling and exports for The Tony Kinnett Cast."""
from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import sys

import numpy as np

SOURCE_ORDER = ("kalshi", "economist", "votehub", "cook", "model_mean", "blend")
FORMATS = {"broadcast": (1920, 1080), "square": (1080, 1080),
           "portrait": (1080, 1350), "portrait_9x16": (1080, 1920)}
NAVY = "#0B165A"
BLUE = "#80C2FC"
WHITE = "#FFFFFF"
DPI = 100


def source_colors():
    return dict(zip(SOURCE_ORDER, ("#58B887", "#F05B61", "#B493DE",
                                   BLUE, BLUE, BLUE)))


def party_colors():
    return {"republican": "#F05B61", "democrat": BLUE,
            "independent": "#EEEAAC", "other": "#B493DE"}


def font_properties(role="body"):
    from matplotlib import font_manager
    family, filename = {
        "body": ("Franklin Gothic Medium Cond", "FRAMDCN.TTF"),
        "headline": ("Franklin Gothic Demi Cond", "FRADMCN.TTF"),
        "emphasis": ("Franklin Gothic Demi Cond", "FRADMCN.TTF"),
    }[role]
    directory = os.environ.get("TKC_FONT_DIR")
    if directory:
        path = Path(directory) / filename
        if path.is_file():
            return font_manager.FontProperties(fname=str(path))
    try:
        path = font_manager.findfont(family, fallback_to_default=False)
        return font_manager.FontProperties(fname=path)
    except ValueError:
        fallback = "BarlowCondensed-Medium.ttf" if role == "body" else "BarlowCondensed-SemiBold.ttf"
        path = Path(__file__).with_name("assets") / "fonts" / fallback
        return font_manager.FontProperties(fname=str(path))


def _wrap(fig, text, font, size, width):
    lines = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        artist = fig.text(0, 0, trial, fontproperties=font, fontsize=size * 72 / DPI)
        measured = artist.get_window_extent(fig.canvas.get_renderer()).width
        artist.remove()
        if current and measured > width:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return "\n".join(lines)


@dataclass
class Canvas:
    fig: object
    W: int
    H: int
    plot_rect: tuple
    scale: float

    def fp(self, role):
        return font_properties(role)

    def axes(self, left_pad=0, right_pad=0, bottom_pad=0, top_pad=0):
        x0, y0, x1, y1 = self.plot_rect
        width = x1 - x0 - left_pad - right_pad
        height = y1 - y0 - bottom_pad - top_pad
        if min(width, height) <= 0:
            raise ValueError("Chart labels leave no plotting area")
        ax = self.fig.add_axes(((x0 + left_pad) / self.W, (y0 + bottom_pad) / self.H,
                                width / self.W, height / self.H), facecolor=NAVY)
        from matplotlib import font_manager
        body_font = self.fp("body")
        font_manager.fontManager.addfont(body_font.get_file())
        # Chart typography uses 28px supporting labels and 34px axis titles.
        label_size = 28 * self.scale * 72 / DPI
        ax.tick_params(which="both", colors=BLUE, labelsize=label_size, length=0,
                       labelfontfamily=body_font.get_name())
        for axis in (ax.xaxis, ax.yaxis):
            axis.label.set_fontproperties(self.fp("emphasis"))
            axis.label.set_fontsize(34 * self.scale * 72 / DPI)
            axis.label.set_color(WHITE)
            offset = axis.get_offset_text()
            offset.set_fontproperties(body_font)
            offset.set_fontsize(label_size)
            offset.set_color(BLUE)
        for spine in ax.spines.values():
            spine.set_visible(False)
        return ax


def make_canvas(title, *, subtitle, source, fmt="broadcast", logo_size="medium"):
    from matplotlib.backends.backend_agg import FigureCanvasAgg, RendererAgg
    from matplotlib.figure import Figure
    from PIL import Image

    width, height = FORMATS[fmt]
    scale = min(width, height) / 1080
    headline_font = font_properties("headline")
    body_font = font_properties()
    fig = Figure(figsize=(width / DPI, height / DPI), dpi=DPI, facecolor=NAVY)
    FigureCanvasAgg(fig)
    margin_x = width * .05
    margin_y = height * (.12 if fmt == "portrait_9x16" else .05)
    top = height - margin_y
    title_text = _wrap(fig, title, headline_font, 66 * scale, width - 2 * margin_x)
    headline = fig.text(margin_x / width, top / height, title_text, va="top",
                        color=WHITE, fontproperties=headline_font, fontsize=66 * scale * 72 / DPI)
    # Measure visible glyphs so the title/subtitle gap follows the artwork.
    renderer = RendererAgg(width, height, DPI)
    headline.draw(renderer)
    ys, _ = np.where(np.asarray(renderer.buffer_rgba())[:, :, 3] > 0)
    title_bottom = height - 1 - ys.max() if len(ys) else headline.get_window_extent().y0
    subtitle_text = _wrap(fig, subtitle, body_font, 36 * scale, width - 2 * margin_x)
    sub = fig.text(margin_x / width, (title_bottom - 12 * scale) / height,
                   subtitle_text, va="top", color=BLUE, fontproperties=body_font,
                   fontsize=36 * scale * 72 / DPI)
    divider_y = sub.get_window_extent(fig.canvas.get_renderer()).y0 - 18 * scale
    from matplotlib.lines import Line2D
    fig.add_artist(Line2D([margin_x / width, 1 - margin_x / width],
                         [divider_y / height] * 2, transform=fig.transFigure,
                         color=BLUE, linewidth=2 * scale * 72 / DPI))

    logo = Image.open(Path(__file__).with_name("assets") / "tkc-logo.png").convert("RGBA")
    logo = logo.crop(logo.getbbox())
    logo_height = min(width, height) * {"small": .075, "medium": .10, "large": .125}[logo_size]
    logo_width = logo_height * logo.width / logo.height
    clear = logo_height * .206
    logo_x = width - margin_x - logo_width
    source_width = logo_x - clear - margin_x
    source_text = _wrap(fig, source, body_font, 28 * scale, source_width)
    note = fig.text(margin_x / width, (margin_y + logo_height / 2) / height,
                    source_text, va="center", color=WHITE, fontproperties=body_font,
                    fontsize=28 * scale * 72 / DPI)
    source_box = note.get_window_extent(fig.canvas.get_renderer())
    if source_box.y0 < margin_y:
        note.set_y((margin_y + source_box.height / 2) / height)
    logo_axes = fig.add_axes((logo_x / width, margin_y / height,
                             logo_width / width, logo_height / height))
    logo_axes.imshow(logo)
    logo_axes.set_axis_off()
    footer_top = max(margin_y + logo_height,
                     note.get_window_extent(fig.canvas.get_renderer()).y1)
    bottom = footer_top + 24 * scale
    plot_top = divider_y - 24 * scale
    if plot_top - bottom < height * .25:
        raise ValueError("Title, subtitle, and sources leave insufficient chart space")
    return Canvas(fig, width, height, (margin_x, bottom, width - margin_x, plot_top), scale)


def bar_chart(canvas, labels, values, *, colors=None, value_fmt="{:,.0f}", sort=True):
    """Draw horizontal bars with a zero baseline and direct value labels."""
    labels = list(labels)
    values = np.asarray(values, dtype=float)
    if not len(labels) or len(labels) != len(values) or len(set(labels)) != len(labels):
        raise ValueError("Supply nonempty, unique labels and matching values")
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Bars require finite nonnegative values")
    order = np.argsort(-values, kind="stable") if sort else np.arange(len(values))
    labels = [labels[index] for index in order]
    values = values[order]
    format_value = value_fmt if callable(value_fmt) else value_fmt.format
    font = canvas.fp("body")
    size = 30 * canvas.scale
    widths = []
    for text in labels + [format_value(value) for value in values]:
        artist = canvas.fig.text(0, 0, text, fontproperties=font, fontsize=size * 72 / DPI)
        widths.append(artist.get_window_extent(canvas.fig.canvas.get_renderer()).width)
        artist.remove()
    ax = canvas.axes(left_pad=max(widths[:len(labels)]) + 16 * canvas.scale,
                     right_pad=max(widths[len(labels):]) + 16 * canvas.scale)
    ax.barh(labels, values, height=.68, color=[(colors or {}).get(label, BLUE) for label in labels])
    ax.invert_yaxis()
    ax.set_xlim(0, max(float(values.max()), 1.0))
    ax.set_xticks([])
    ax.set_yticks([])
    for index, (label, value) in enumerate(zip(labels, values)):
        for text, position, offset, align in (
            (label, 0, -14, "right"), (format_value(value), value, 10, "left")
        ):
            ax.annotate(text, (position, index), xytext=(offset * canvas.scale * 72 / DPI, 0),
                        textcoords="offset points", ha=align, va="center", color=WHITE,
                        fontproperties=font, fontsize=size * 72 / DPI, annotation_clip=False)
    return ax


def renderer():
    """Return the canvas and chart interfaces used by the analysis notebooks."""
    module = sys.modules[__name__]
    return module, module


def save_chart(canvas, name, *, out_dir, script=None, scratch_dir=None):
    from PIL import Image
    if not name or Path(name).name != name or name in (".", ".."):
        raise ValueError("Chart name must be a filename stem")
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    png = output / f"{name}.png"
    canvas.fig.savefig(png, dpi=DPI, facecolor=NAVY)
    paths = {"png": png}
    if script:
        destination = output / f"{name}.py"
        if Path(script).resolve() != destination.resolve():
            shutil.copyfile(script, destination)
        paths["source"] = destination
    if scratch_dir:
        scratch = Path(scratch_dir)
        scratch.mkdir(parents=True, exist_ok=True)
        with Image.open(png) as image:
            for label, width in (("dest", 960), ("thumb", 320)):
                path = scratch / f"{name}_{label}.png"
                image.resize((width, round(width * canvas.H / canvas.W)), Image.Resampling.LANCZOS).save(path)
                paths[f"check_{label}"] = path
    return paths


def graphics_assets():
    """Identify the actual logo and font files without recording machine paths."""
    from .data import sha256

    logo = Path(__file__).with_name("assets") / "tkc-logo.png"
    assets = {"logo": {"filename": logo.name, "status": "available" if logo.is_file() else "unavailable"}, "fonts": {}}
    if logo.is_file():
        assets["logo"]["sha256"] = sha256(logo)
    for role in ("headline", "body", "emphasis"):
        try:
            font = font_properties(role)
            path = Path(font.get_file())
            assets["fonts"][role] = {
                "filename": path.name, "family": font.get_name(), "sha256": sha256(path),
                "status": "available", "fallback": font.get_name() == "Barlow Condensed",
            }
        except (ImportError, RuntimeError, FileNotFoundError) as error:
            assets["fonts"][role] = {"status": "unavailable", "reason": type(error).__name__}
    return assets
