import json
from pathlib import Path
import runpy

import pytest

from congress_scorecard.data import project_root, sha256
from congress_scorecard.plotting import font_properties, graphics_assets, make_canvas, save_chart


@pytest.fixture
def chart():
    try:
        font_properties()
        font_properties("headline")
    except RuntimeError as error:
        pytest.skip(str(error))
    return make_canvas("Geometry check", subtitle="Illustrative test.",
                       source="Source: Software test data.")


def test_chart_lint_rejects_dimensions_and_outside_text(chart, tmp_path):
    from PIL import Image
    from congress_scorecard.chart_lint import lint_chart

    path = save_chart(chart, "valid", out_dir=tmp_path)["png"]
    assert lint_chart(chart, path)["passed"]
    with Image.open(path) as image:
        image.resize((100, 100)).save(path)
    assert "Export dimensions differ" in " ".join(lint_chart(chart, path)["failures"])
    path = save_chart(chart, "outside", out_dir=tmp_path)["png"]
    chart.fig.text(-.1, .5, "Clipped text")
    assert not lint_chart(chart, path)["passed"]


def test_chart_lint_rejects_collisions_and_unreadable_image(chart, tmp_path):
    from congress_scorecard.chart_lint import lint_chart

    chart.fig.text(.4, .5, "First label")
    chart.fig.text(.4, .5, "Second label")
    path = save_chart(chart, "overlap", out_dir=tmp_path)["png"]
    assert "overlaps another" in " ".join(lint_chart(chart, path)["failures"])
    assert not lint_chart(chart, tmp_path / "missing.png")["passed"]


def test_smoke_saves_lint_and_returns_failure(tmp_path, monkeypatch):
    script = project_root() / "scripts/render_smoke.py"
    main = runpy.run_path(str(script))["main"]
    monkeypatch.setitem(main.__globals__, "lint_chart", lambda *args: {
        "passed": False, "failures": ["Deliberate test failure"], "checks": [],
    })
    assert main(["--out", str(tmp_path)]) == 1
    result = json.loads((tmp_path / "lint.json").read_text())
    assert result["passed"] is False
    assert "Deliberate test failure" in result["failures"]


def test_graphics_asset_hashes_match_actual_files():
    assets = graphics_assets()
    assert assets["logo"]["sha256"] == sha256(
        project_root() / "src/congress_scorecard/assets/tkc-logo.png"
    )
    for role, record in assets["fonts"].items():
        if record["status"] == "available":
            path = Path(font_properties(role).get_file())
            assert record["sha256"] == sha256(path)
            assert record["filename"] == path.name
            assert "path" not in record
