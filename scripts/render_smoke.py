"""Render and lint an illustrative chart using the project plotting setup."""
import argparse
import json
from pathlib import Path

from congress_scorecard.chart_lint import lint_chart
from congress_scorecard.data import project_root
from congress_scorecard.plotting import (
    bar_chart, graphics_assets, make_canvas, save_chart, source_colors,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=project_root() / "outputs/plotting-check")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    try:
        canvas = make_canvas(
            "Illustrative comparison checks chart styling",
            subtitle="Synthetic values exercise the fonts and source labels.",
            source="Source: Illustrative software verification data. Values are 200 and 100.",
        )
        colors = source_colors()
        bar_chart(canvas, ["Kalshi", "Economist"], [200, 100],
                  colors={"Kalshi": colors["kalshi"], "Economist": colors["economist"]})
        paths = save_chart(canvas, "plotting-check", out_dir=args.out,
                           script=__file__, scratch_dir=args.out / "previews")
        result = lint_chart(canvas, paths["png"])
    except Exception as error:
        result = {"passed": False, "checks": [], "failures": [str(error)]}
    result["graphics_assets"] = graphics_assets()
    (args.out / "lint.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    status = "PASSED" if result["passed"] else "FAILED"
    print(f"CHART LINT {status}: {args.out / 'lint.json'}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
