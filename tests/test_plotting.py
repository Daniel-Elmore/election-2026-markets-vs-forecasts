import pytest

from congress_scorecard.plotting import party_colors, source_colors


def test_stable_colors():
    colors = source_colors()
    assert colors["kalshi"] == "#58B887"
    assert colors["economist"] == "#F05B61"
    assert colors["votehub"] == "#B493DE"
    assert colors["cook"] == colors["model_mean"] == colors["blend"] == "#80C2FC"
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


@pytest.mark.parametrize("role,filename", [
    ("headline", "BarlowCondensed-SemiBold.ttf"),
    ("emphasis", "BarlowCondensed-SemiBold.ttf"),
    ("body", "BarlowCondensed-Medium.ttf"),
])
def test_missing_franklin_uses_bundled_fallback(monkeypatch, tmp_path, role, filename):
    from matplotlib import font_manager
    from congress_scorecard.plotting import font_properties, graphics_assets

    original = font_manager.findfont

    def without_franklin(family, *args, **kwargs):
        if isinstance(family, str) and family.startswith("Franklin Gothic"):
            raise ValueError("Font unavailable for test")
        return original(family, *args, **kwargs)

    monkeypatch.setattr(font_manager, "findfont", without_franklin)
    monkeypatch.setenv("TKC_FONT_DIR", str(tmp_path))
    font = font_properties(role)
    assert font.get_name() == "Barlow Condensed"
    assert font.get_file().endswith(filename)
    assert graphics_assets()["fonts"][role]["fallback"] is True


def test_partial_explicit_font_directory(monkeypatch, tmp_path):
    import shutil
    from matplotlib import font_manager
    from congress_scorecard.data import project_root
    from congress_scorecard.plotting import font_properties

    source = project_root() / "src/congress_scorecard/assets/fonts/BarlowCondensed-Medium.ttf"
    explicit = tmp_path / "FRAMDCN.TTF"
    shutil.copyfile(source, explicit)
    monkeypatch.setenv("TKC_FONT_DIR", str(tmp_path))
    def unavailable(*args, **kwargs):
        raise ValueError("Font unavailable for test")

    monkeypatch.setattr(font_manager, "findfont", unavailable)
    assert font_properties("body").get_file() == str(explicit)
    assert font_properties("headline").get_file().endswith("BarlowCondensed-SemiBold.ttf")


def test_fallback_smoke_render_passes_lint(monkeypatch, tmp_path):
    import json
    import runpy
    from matplotlib import font_manager
    from congress_scorecard.data import project_root

    original = font_manager.findfont

    def without_franklin(family, *args, **kwargs):
        if isinstance(family, str) and family.startswith("Franklin Gothic"):
            raise ValueError("Font unavailable for test")
        return original(family, *args, **kwargs)

    monkeypatch.delenv("TKC_FONT_DIR", raising=False)
    monkeypatch.setattr(font_manager, "findfont", without_franklin)
    main = runpy.run_path(str(project_root() / "scripts/render_smoke.py"))["main"]
    assert main(["--out", str(tmp_path)]) == 0
    report = json.loads((tmp_path / "lint.json").read_text())
    assert report["passed"]
    assert all(font["fallback"] for font in report["graphics_assets"]["fonts"].values())
