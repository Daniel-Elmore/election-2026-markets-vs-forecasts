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

Chart rendering requires Franklin Gothic Demi Condensed and Franklin Gothic Medium Condensed. Install the fonts or set TKC_FONT_DIR to a directory containing FRADMCN.TTF and FRAMDCN.TTF. The plotting smoke command saves lint results and returns a nonzero exit code if rendering or automated checks fail. Visual review is also required for final figures.

Choose a results snapshot explicitly when validating or running notebooks. The current-partial snapshot contains preliminary recorded results. The ddhq-20261104-222052-est snapshot has documented House control derived from district calls. The synthetic-complete snapshot supplies invented software test data. For independent notebook execution, set CONGRESS_SCORECARD_SNAPSHOT before launching the notebook frontend.

Runs preserve earlier outputs under outputs/<snapshot>/<run-id>/. Each run records inputs, source code, dependencies, and graphics asset hashes. See the [data and scoring guide](docs/data-and-scoring.md) for schemas, interfaces, new snapshot preparation, and execution options.

## Notebooks

| Part | Notebook | Focus |
| --- | --- | --- |
| 1 | [Congress scorecard](notebooks/01_congress_scorecard.ipynb) | Calls, seats, control, and the biggest forecast misses |
| 2 | [Forecast accuracy](notebooks/02_forecast_accuracy.ipynb) | Proper scores, paired comparisons, calibration, and vote-share error |
| 3 | [Kalshi trading volume](notebooks/03_kalshi_trading_volume.ipynb) | Volume concentration and how forecast comparisons change with volume |

The notebooks currently contain analysis outlines. The [analysis plan](docs/analysis-plan.md) defines the scoring rules and comparisons. The [data guide](data/README.md) describes the recorded inputs and their limitations.

## License

The project’s original software code is licensed under the [MIT License](LICENSE). Third-party data and source captures remain subject to their respective terms. The TKC logo and branding remain subject to their respective rights.
