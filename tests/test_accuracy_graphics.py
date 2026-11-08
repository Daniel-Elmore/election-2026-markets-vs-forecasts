"""Targeted rendering checks for the forecast-accuracy presentation."""
import ast
from pathlib import Path
from types import SimpleNamespace

import nbformat
import numpy as np
import pandas as pd
import pytest
from matplotlib.text import Text


@pytest.fixture(params=[False, True], ids=["franklin", "barlow"])
def graphics(request, monkeypatch, tmp_path):
    if request.param:
        from matplotlib import font_manager
        original = font_manager.findfont
        def without_franklin(family, *args, **kwargs):
            if isinstance(family, str) and family.startswith("Franklin Gothic"):
                raise ValueError("Unavailable for fallback verification")
            return original(family, *args, **kwargs)
        monkeypatch.setattr(font_manager, "findfont", without_franklin)
        monkeypatch.setenv("TKC_FONT_DIR", str(tmp_path))
    path = Path(__file__).resolve().parents[1] / "notebooks/02_forecast_accuracy.ipynb"
    book = nbformat.read(path, 4)
    namespace = {}
    for cell in book.cells:
        if "imports" in cell.metadata.get("tags", []):
            exec(compile(cell.source, "accuracy_imports", "exec"), namespace)
    cell = next(c for c in book.cells if c.cell_type == "code" and "def dot_chart" in c.source)
    names = {"SYMBOL_PATH", "SYMBOL_FONT", "SYMBOL_FONTS", "STATE_NAMES", "SAMPLE_NAMES"}
    nodes = [n for n in ast.parse(cell.source).body
             if isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef)) or
             (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets))]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "accuracy_graphics", "exec"), namespace)
    namespace["inputs"] = SimpleNamespace(snapshot_id="test-real", manifest={"synthetic": False})
    namespace["colors"] = namespace["source_colors"]()
    captured = []
    namespace["save_figure"] = lambda name, canvas, data: captured.append((name, canvas, data))
    return namespace, captured


def test_bar_marks_and_typography(graphics):
    h, captured = graphics
    data = pd.DataFrame({"source": ["Kalshi", "VoteHub"], "value": [.094463, .117721]})
    h["bar_chart"]("test", "Checking Bar Scores", "Recorded values.", data,
                   label="source", value="value", note="Software verification.")
    _, canvas, _ = captured[0]
    canvas.fig.canvas.draw()
    axes = [a for a in canvas.fig.axes if a.patches][0]
    assert axes.get_xlim()[0] == 0
    np.testing.assert_allclose([p.get_width() for p in axes.patches], data.value)
    assert axes.xaxis.labelpad == pytest.approx(4 + 16 * .72)
    labels = [t for t in canvas.fig.findobj(match=Text) if t.get_text() in data.source.tolist()]
    assert len(labels) == 2
    assert all(t.get_fontsize() == 23 and t.get_color() == "white" for t in labels)
    assert {t.get_text() for t in axes.texts} == {"0.0945", "0.1177"}
    assert all(t.get_fontsize() == 25 for t in axes.texts)


def test_longshot_groups_zero_labels_counts_and_exact_total(graphics):
    h, captured = graphics
    data = pd.DataFrame({"band": ["0–<5%", "5–<10%", "10–<25%", "25–<50%"],
                         "n": [18, 5, 4, 5], "observed_wins": [0, 0, 0, 1],
                         "expected_wins": [.327, .334, .750, 1.570]})
    h["longshot_chart"](data)
    _, canvas, plotted = captured[0]
    canvas.fig.canvas.draw()
    axes = [a for a in canvas.fig.axes if a.patches][0]
    assert axes.get_xlim()[0] == 0
    np.testing.assert_allclose([p.get_width() for p in axes.patches], [0, 0, 0, 1, .327, .334, .75, 1.57])
    assert sum(t.get_text() == "0" for t in axes.texts) == 3
    assert plotted.expected_total.eq(2.981).all()
    assert plotted.observed_total.eq(1).all()
    text = [t.get_text() for t in canvas.fig.findobj(match=Text)]
    assert "1 Observed Win · 2.98 Expected" in text
    assert all(f"{b} (n={n})" in text for b, n in zip(data.band, data.n))
    assert all(t.get_fontsize() == 23 for t in canvas.fig.findobj(match=Text)
               if t.get_text() in ("Observed", "Expected"))
    keys = [t for t in canvas.fig.findobj(match=Text) if t.get_text() in ("Observed", "Expected")]
    assert all(t.get_window_extent().x0 > axes.get_window_extent().x1 for t in keys)
    assert np.mean([t.get_window_extent().y0 + t.get_window_extent().height / 2 for t in keys]) == pytest.approx(
        axes.get_window_extent().y0 + axes.get_window_extent().height / 2, abs=1)


def test_complete_power_curves_collapse_and_share_scale(graphics):
    h, captured = graphics
    rows = []
    for sample, count, base in [("all", 35, .02), ("non_solid", 15, .06)]:
        for design in ["planned", "eligible"]:
            for rho in [0., .1, .25, .5]:
                rows.append({"sample": sample, "design": design, "n": count,
                             "rho_latent": rho, "detectable_gap_80pct": base + .04 * rho})
    h["power_chart"](pd.DataFrame(rows))
    _, canvas, plotted = captured[0]
    canvas.fig.canvas.draw()
    axes = [a for a in canvas.fig.axes if a.lines]
    assert len(axes) == 2 and all(len(a.lines) == 1 for a in axes)
    assert axes[0].get_ylim() == axes[1].get_ylim()
    assert len(plotted) == 16
    text = [t.get_text() for t in canvas.fig.findobj(match=Text)]
    assert "Planned = Scored (n=35)" in text and "Planned = Scored (n=15)" in text
    assert "ρ" in text
    assert all(t.get_fontsize() == 23 for t in canvas.fig.findobj(match=Text)
               if t.get_text().startswith("Planned = Scored"))
    assert all(t.get_fontsize() == 28 for t in canvas.fig.findobj(match=Text)
               if t.get_text() in ("All Races", "Non-Solid"))
    assert axes[0].yaxis.labelpad == pytest.approx(4 + 8 * .72)
    assert all(t.get_window_extent().y1 < axes[0].get_window_extent().y0 - 70
               for t in canvas.fig.findobj(match=Text) if t.get_text().startswith("Planned = Scored"))


def test_symbol_baseline_and_portable_provenance(graphics):
    h, _ = graphics
    canvas = h["chart_canvas"]("Checking Symbol Baselines", "One mixed-font line.", "Software test.")
    box = h["rich_text"](canvas, 500, 500, "Latent ρ = 0", size=23)
    canvas.fig.canvas.draw()
    texts = box.findobj(match=Text)
    baselines = [t.get_transform().transform(t.get_position())[1] for t in texts]
    assert max(baselines) - min(baselines) < .5
    symbol = next(t for t in texts if t.get_text() == "ρ")
    assert Path(symbol.get_fontproperties().get_file()) == h["SYMBOL_PATH"]
    assert symbol.get_fontsize() == 23
    assert h["SYMBOL_FONTS"][0]["characters"] == ["ρ"]
    assert h["SYMBOL_FONTS"][0]["role"] == "rho_symbol"
    assert h["STATE_NAMES"]["NC"] == "North Carolina"
    assert h["STATE_NAMES"]["NH"] == "New Hampshire"


def test_difference_bars_sort_and_start_at_zero(graphics):
    h, captured = graphics
    data = pd.DataFrame({"state": ["Texas", "Kansas", "Florida", "Maine"],
                         "difference": [.02, -.1, -.1, 0.], "race_id": ["TX-SEN", "KS-SEN", "FL-SEN", "ME-SEN"]})
    h["difference_bars"]("test", "Comparing Losses", data, label="state", value="difference",
                         xlabel="Brier Difference", subtitle="One matched comparison per race.", note="Software test.")
    _, canvas, plotted = captured[0]
    axes = next(a for a in canvas.fig.axes if a.patches)
    assert plotted.state.tolist() == ["Florida", "Kansas", "Maine", "Texas"]
    np.testing.assert_allclose([p.get_width() for p in axes.patches], plotted.difference)
    assert all(p.get_x() == 0 for p in axes.patches)
    assert set(plotted.race_id) == set(data.race_id)
    from matplotlib.colors import to_rgba
    assert [p.get_facecolor() for p in axes.patches] == [to_rgba(h["colors"]["kalshi"])] * 3 + [to_rgba("#80C2FC")]
    assert [t.get_text() for t in axes.texts] == ["0"]


@pytest.mark.parametrize("complete", [False, True])
def test_power_legend_rows_are_centered_below_each_panel(graphics, complete):
    h, captured = graphics
    rows = []
    for sample, planned, scored in [("all", 35, 33), ("non_solid", 15, 13)]:
        for design in ["planned", "eligible"]:
            for rho in [0., .1, .25, .5]:
                rows.append({"sample": sample, "design": design,
                             "n": planned if complete or design == "planned" else scored,
                             "rho_latent": rho, "detectable_gap_80pct": .03 + rho * .1 +
                             (.005 if not complete and design == "eligible" else 0)})
    h["power_chart"](pd.DataFrame(rows))
    _, canvas, _ = captured[0]
    canvas.fig.canvas.draw()
    axes = [a for a in canvas.fig.axes if a.lines]
    labels = [t for t in canvas.fig.findobj(match=Text) if t.get_text().startswith(("Planned", "Scored"))]
    for ax in axes:
        panel = ax.get_window_extent()
        bounds = sorted([t.get_window_extent() for t in labels if panel.x0 < t.get_window_extent().x0 < panel.x1], key=lambda b:b.x0)
        assert len(bounds) == (1 if complete else 2)
        left, right = bounds[0].x0 - 52 * canvas.scale, bounds[-1].x1
        assert (left + right) / 2 == pytest.approx((panel.x0 + panel.x1) / 2, abs=1)
        assert left >= panel.x0 and right <= panel.x1
        assert max(b.y0 for b in bounds) - min(b.y0 for b in bounds) < .5
        assert max(b.y1 for b in bounds) < panel.y0 - 95
        assert min(b.y0 for b in bounds) > canvas.plot_rect[1]


def test_scorecard_two_and_eight_move_up_and_legend_is_centered(graphics):
    h, _ = graphics
    from congress_scorecard.data import load_inputs
    book = nbformat.read(Path(__file__).resolve().parents[1] / "notebooks/01_congress_scorecard.ipynb", 4)
    namespace = {}
    nodes = [n for n in ast.parse(book.cells[1].source).body if isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef))]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "scorecard_helpers", "exec"), namespace)
    data = load_inputs(snapshot="ddhq-20261104-222052-est")
    namespace.update(data=data, senate=data.senate, colors=h["colors"], BLUE="#80C2FC", GOLD="#EEEAAC",
                     synthetic=False, score_records={}, layout_checks={},
                     SOURCES={"Kalshi":("p_kalshi","kalshi"),"Economist":("p_economist","economist"),
                              "VoteHub Complete":("p_votehub","votehub"),"Cook":("p_cook_primary","cook")},
                     display_names={"Kalshi":"Kalshi","Economist":"The Economist","VoteHub Complete":"VoteHub","Cook":"Cook"})
    for name in ["say","save_table","present"]:
        namespace[name] = lambda *args, **kwargs: None
    captured = []
    namespace["export_chart"] = lambda cv, stem, frame: captured.append((cv, stem))
    for index in [5,13]:
        exec(compile(book.cells[index].source, "scorecard_charts", "exec"), namespace)
    assert [stem for _,stem in captured] == ["02-expected-wins","08-cook-rating-outcomes"]
    for canvas, stem in captured:
        canvas.fig.canvas.draw()
        assert canvas.plot_rect[3] - canvas.fig.axes[-1].get_window_extent().y1 == pytest.approx(0 if stem.startswith("02") else 24)
        assert canvas.fig.axes[-1].xaxis.labelpad == pytest.approx(4+16*.72)
        if stem.startswith("08"):
            legend = namespace["layout_checks"][stem]
            bounds = legend["legend_bounds"]
            assert len({round(b[1],4) for b in bounds}) == 1
            assert ((bounds[0][0]-34*canvas.scale)+bounds[-1][0]+bounds[-1][2])/2 == pytest.approx(canvas.W/2,abs=1)
            assert bounds[0][1]+bounds[0][3] < canvas.fig.axes[-1].get_window_extent().y0
            footer = canvas.fig.texts[2].get_window_extent()
            assert min(b[1] for b in bounds) - footer.y1 > 24


def test_row_guides_preserve_zoomed_influence_values(graphics):
    h, captured = graphics
    data = pd.DataFrame({"state": ["Kansas", "Texas"], "value": [-.04, -.05]})
    h["dot_chart"]("test", "Influence", data, label="state", value="value", xlabel="Paired Difference",
                   subtitle="Each omission leaves one fewer pair.", note="Influence, not uncertainty.",
                   zero_reference=False, row_guides=True)
    _, canvas, _ = captured[0]
    axes = next(a for a in canvas.fig.axes if a.collections)
    assert "Zoomed Scale" in axes.get_xlabel()
    assert len(axes.lines) == 2
    np.testing.assert_allclose([c.get_offsets()[0, 0] for c in axes.collections], data.value)
    assert axes.get_xlim()[1] < 0


def test_all_subtitle_branches_fit_at_original_size(graphics):
    h, _ = graphics
    root = Path(__file__).resolve().parents[1]

    def variants(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return [node.value]
        if isinstance(node, ast.IfExp):
            return variants(node.body) + variants(node.orelse)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return [a + b for a in variants(node.left) for b in variants(node.right)]
        if isinstance(node, ast.JoinedStr):
            return ["".join(v.value if isinstance(v, ast.Constant) else "35" for v in node.values)]
        return []

    checked = 0
    for part in ["01_congress_scorecard", "02_forecast_accuracy"]:
        book = nbformat.read(root / "notebooks" / (part + ".ipynb"), 4)
        for cell in book.cells:
            if cell.cell_type != "code":
                continue
            for node in ast.walk(ast.parse(cell.source)):
                expression = None
                if isinstance(node, ast.keyword) and node.arg == "subtitle":
                    expression = node.value
                elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "subtitle" for t in node.targets):
                    expression = node.value
                if expression is None:
                    continue
                for subtitle in variants(expression):
                    canvas = h["make_canvas"]("Subtitle Fit", subtitle=subtitle, source="Software verification.")
                    assert "\n" not in canvas.fig.texts[1].get_text(), subtitle
                    assert canvas.fig.texts[1].get_fontsize() == pytest.approx(36 * .72)
                    canvas.fig.clear()
                    checked += 1
    assert checked >= 20


def test_shared_divider_and_axis_spacing(graphics):
    h, _ = graphics
    canvas = h["make_canvas"]("Checking Spacing", subtitle="One line.", source="Software verification.")
    axes = canvas.axes()
    assert axes.xaxis.labelpad == pytest.approx(4 + 16 * .72)
    canvas.fig.canvas.draw()
    subtitle = canvas.fig.texts[1].get_window_extent(canvas.fig.canvas.get_renderer())
    from matplotlib.lines import Line2D
    divider = next(a for a in canvas.fig.artists if isinstance(a, Line2D))
    assert subtitle.y0 - divider.get_ydata()[0] * canvas.H == pytest.approx(12)


def test_notebook_one_comparison_columns_are_measured(graphics):
    h, _ = graphics
    from congress_scorecard.data import load_inputs
    book = nbformat.read(Path(__file__).resolve().parents[1] / "notebooks/01_congress_scorecard.ipynb", 4)
    namespace = {}
    nodes = [n for n in ast.parse(book.cells[1].source).body if isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef))]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "scorecard_helpers", "exec"), namespace)
    data = load_inputs(snapshot="ddhq-20261104-222052-est")
    namespace.update(data=data, senate=data.senate, colors=h["colors"] if "colors" in h else h["source_colors"](),
                     BLUE="#80C2FC", GOLD="#EEEAAC", synthetic=False, score_records={}, layout_checks={})
    namespace["say"] = lambda *args: None
    namespace["save_table"] = lambda *args, **kwargs: None
    captured = []
    namespace["export_chart"] = lambda cv, stem, frame: captured.append((cv, stem))
    exec(compile(book.cells[9].source, "comparison_charts", "exec"), namespace)
    assert len(captured) == 3
    for canvas, stem in captured:
        canvas.fig.canvas.draw()
        layout = namespace["layout_checks"][stem]
        assert layout["plot_right_px"] - layout["plot_left_px"] > 814
        axes = canvas.fig.axes[-1]
        assert axes.get_window_extent().height > 540
        assert canvas.plot_rect[3] - axes.get_window_extent().y1 == pytest.approx(24)
        renderer = canvas.fig.canvas.get_renderer()
        row_bounds = [t.get_window_extent(renderer) for t in axes.texts]
        assert min(b.x0 for b in row_bounds) == pytest.approx(canvas.plot_rect[0], abs=1)
        assert max(b[0] + b[2] for b in layout["legend_label_bounds"]) == pytest.approx(canvas.plot_rect[2], abs=1)
