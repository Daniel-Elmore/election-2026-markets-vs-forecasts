import pytest

from congress_scorecard.plotting import party_colors, source_colors


def test_stable_colors():
    colors = source_colors()
    assert colors["kalshi"] == "#EEEAAC"
    assert colors["economist"] == "#58B887"
    assert colors["kalshi"] != colors["economist"]
    assert party_colors()["democrat"] == "#80C2FC"


def test_chart_export_and_invalid_values(tmp_path):
    pytest.importorskip("matplotlib")
    from PIL import Image
    from congress_scorecard.plotting import bar_chart, font_properties, make_canvas, save_chart

    try:
        font_properties()
        font_properties("headline")
    except RuntimeError as error:
        pytest.skip(str(error))
    canvas = make_canvas(
        "Example comparison",
        subtitle="Illustrative values are 200 and 100.",
        source="Source: Software test data.",
    )
    ax = bar_chart(canvas, ["A", "B"], [200, 100])
    assert ax.get_xlim()[0] == 0
    assert [bar.get_width() for bar in ax.patches] == [200, 100]
    for labels, values in ((["A"], [-1]), (["A"], [float("nan")]), ([], [])):
        with pytest.raises(ValueError):
            bar_chart(canvas, labels, values)
    paths = save_chart(canvas, "example", out_dir=tmp_path, scratch_dir=tmp_path / "previews")
    with Image.open(paths["png"]) as image:
        assert image.size == (1920, 1080)
    assert paths["check_dest"].is_file()
    assert paths["check_thumb"].is_file()


def test_generic_axes_follow_tkc_typography_after_tick_changes():
    pytest.importorskip("matplotlib")
    from matplotlib.ticker import AutoMinorLocator
    from congress_scorecard.plotting import BLUE, WHITE, font_properties, make_canvas

    canvas = make_canvas("Axis typography check", subtitle="Illustrative scientific notation.",
                         source="Source: Software test data.")
    ax = canvas.axes(left_pad=120, bottom_pad=100)
    ax.plot([1000000, 2000000], [1, 2])
    ax.set_xlabel("Recorded volume")
    ax.set_ylabel("Forecast gap")
    ax.xaxis.set_minor_locator(AutoMinorLocator())
    canvas.fig.canvas.draw()
    # New ticks created after the first draw must keep the same styling.
    ax.set_xticks([1000000, 1250000, 1500000, 1750000, 2000000])
    canvas.fig.canvas.draw()
    body = font_properties("body")
    emphasis = font_properties("emphasis")
    for axis in (ax.xaxis, ax.yaxis):
        for label in axis.get_ticklabels(which="both"):
            assert label.get_fontproperties().get_name() == body.get_name()
            assert label.get_fontsize() == pytest.approx(28 * 72 / 100)
            assert label.get_color() == BLUE
        assert axis.label.get_fontproperties().get_file() == emphasis.get_file()
        assert axis.label.get_fontsize() == pytest.approx(34 * 72 / 100)
        assert axis.label.get_color() == WHITE
        assert axis.get_offset_text().get_fontproperties().get_file() == body.get_file()
        assert axis.get_offset_text().get_color() == BLUE
