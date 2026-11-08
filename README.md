# 2026 Election — Markets vs. Forecasts

A comparison of the November 2, 2026 prediction-market and forecast snapshots for 35 Senate races and House control.

## Quick start

Use Python 3.12 or later. Run these commands from the repository root in PowerShell.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[notebooks,plotting,audit,test]"
python -m pip check
python scripts/validate_inputs.py --snapshot current-partial
python -m pytest -q
python scripts/render_smoke.py
python scripts/run_notebooks.py --snapshot current-partial
```

Charts prefer Franklin Gothic Demi Condensed and Franklin Gothic Medium Condensed when installed. Otherwise, they automatically use the included free Barlow Condensed SemiBold and Medium fonts. Rendering works offline without installing fonts. TKC_FONT_DIR optionally selects a directory containing FRADMCN.TTF and FRAMDCN.TTF. The plotting smoke command saves lint results and returns a nonzero exit code if rendering or automated checks fail. Visual review is also required for final figures.

Choose a results snapshot explicitly when validating or running notebooks. The current-partial snapshot contains preliminary recorded results. The ddhq-20261104-222052-est snapshot has documented House control derived from district calls. The synthetic-complete snapshot supplies invented software test data. For independent notebook execution, set CONGRESS_SCORECARD_SNAPSHOT before launching the notebook frontend.

Runs preserve earlier outputs under outputs/<snapshot>/<run-id>/. Each run records inputs, source code, dependencies, and graphics asset hashes. See the [data and scoring guide](docs/data-and-scoring.md) for schemas, interfaces, new snapshot preparation, and execution options.

## Publishing the Scorecard

Execution preserves a new run under `outputs/`; it does not update the GitHub-facing notebook or published figures. Run the selected snapshot, review its results and every graphic, then promote that exact run:

```powershell
python scripts/run_notebooks.py --snapshot ddhq-20261104-222052-est
python scripts/publish_scorecard.py --run outputs/ddhq-20261104-222052-est/<run-id> --reviewed
```

Replace `<run-id>` with the successful runner's directory name. `--reviewed` confirms that you completed numerical and visual review; automated checks do not establish visual approval. Publication validates the run and promotes its executed scorecard notebook, PNGs, plotted-data CSVs, and portable provenance together. Synthetic runs cannot be published. See the [publication procedure](docs/data-and-scoring.md#publishing-a-reviewed-scorecard-run) for checks and recovery behavior.

## Notebooks

| Part | Notebook | Focus |
| --- | --- | --- |
| 1 | [Congress scorecard](notebooks/01_congress_scorecard.ipynb) | Calls, seats, control, and the biggest forecast misses |
| 2 | [Forecast accuracy](notebooks/02_forecast_accuracy.ipynb) | Proper scores, paired comparisons, calibration, and vote-share error |
| 3 | [Kalshi trading volume](notebooks/03_kalshi_trading_volume.ipynb) | Volume concentration and how forecast comparisons change with volume |

The Congress scorecard and forecast-accuracy notebooks contain executed analyses and figures. Forecast accuracy leads with the paired Kalshi-versus-mixed-mean Brier contrast, with conditional uncertainty and dependence diagnostics. Real vote-share comparisons remain unavailable pending completeness and target-compatibility evidence. The trading-volume notebook remains an outline. The [analysis plan](docs/analysis-plan.md) defines the scoring rules and comparisons. The [data guide](data/README.md) describes the recorded inputs and their limitations.

To publish a reviewed forecast-accuracy run, use `python scripts/publish_scorecard.py --run outputs/ddhq-20261104-222052-est/<run-id> --part 02_forecast_accuracy --reviewed`. Omitting `--part` retains Congress scorecard publication. Each command promotes only the selected notebook and its figures, plotted CSVs, and provenance.

## License

The project’s original software code is licensed under the [MIT License](LICENSE). Third-party data and source captures remain subject to their respective terms. The TKC logo and branding remain subject to their respective rights. Bundled Barlow Condensed fonts use the included [SIL Open Font License](src/congress_scorecard/assets/fonts/OFL.txt).
