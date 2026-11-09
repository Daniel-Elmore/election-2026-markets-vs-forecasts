# 2026 Election — Markets vs. Forecasts

How did prediction markets and election forecasters compare in the 2026 congressional elections? This project evaluates frozen November 2 forecasts covering 35 Senate races and House control, then examines how the comparisons change with Kalshi trading volume.

## Key results

The published analyses use the November 4 DDHQ archive (`ddhq-20261104-222052-est`). These findings describe that preliminary snapshot.

| Finding | Result |
| --- | --- |
| House control | DDHQ district calls reached the 218-seat threshold for Democrats. Kalshi, The Economist, and VoteHub Complete each favored Democratic control. |
| Senate forecast accuracy | Raw Kalshi's mean Brier score was 0.043 lower than the equal-weight Economist/VoteHub Complete benchmark across 13 of 15 planned primary pairs. The comparison is provisional, and VoteHub Complete incorporates market information. |
| Trading concentration | Recorded Senate market volume totaled $212.2 million. Texas accounted for $76.4 million, or 36.0% of the total. |

## Skills and methods

- **Forecast evaluation** with paired Brier-score comparisons, calibration diagnostics, and bootstrap sensitivity checks.
- **Monte Carlo simulation** to examine calibration and statistical power under different assumptions about dependence across races.
- **Reproducible analysis** with Python, pandas, NumPy, Matplotlib, and Jupyter, using named snapshots and checksums for published inputs and artifacts.

## Project overview

| Analysis | Executed notebook | Figures and plotted data |
| --- | --- | --- |
| Congress scorecard | [Calls, control, and forecast misses](notebooks/01_congress_scorecard.ipynb) | [Scorecard figures](figures/01_congress_scorecard/) |
| Forecast accuracy | [Brier scores, paired comparisons, calibration, and simulation](notebooks/02_forecast_accuracy.ipynb) | [Accuracy figures](figures/02_forecast_accuracy/) |
| Kalshi trading volume | [Volume concentration and sensitivity to a $250,000 cutoff](notebooks/03_kalshi_trading_volume.ipynb) | [Trading-volume figures](figures/03_kalshi_trading_volume/) |

## Data and limitations

The frozen inputs cover Kalshi, The Economist, and VoteHub Complete forecasts, Cook Political Report race ratings, and DDHQ results. Scoring coverage varies by metric and snapshot. Real vote-share comparisons require documented completeness and compatibility with the forecast target. See the [data inventory](data/README.md), [scoring guide](docs/data-and-scoring.md), and [analysis plan](docs/analysis-plan.md).

## Repository structure

| Directory | Contents |
| --- | --- |
| `notebooks/` | Three executed analyses with editable code |
| `figures/` | Published PNGs, plotted CSVs, and run provenance |
| `data/` | Frozen inputs, named results snapshots, and evidence |
| `docs/` | Analysis plan and scoring documentation |
| `src/`, `scripts/`, `tests/` | Shared code, execution and publication commands, and automated checks |

## Quick start

Use Python 3.12 or later. Run these commands from the repository root in PowerShell.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[notebooks,plotting,audit,test]"
python -m pip check
python scripts/validate_inputs.py --snapshot ddhq-20261104-222052-est
python -m pytest -q
python scripts/render_smoke.py
python scripts/run_notebooks.py --snapshot ddhq-20261104-222052-est
```

Charts prefer Franklin Gothic Demi Condensed and Franklin Gothic Medium Condensed when installed. Otherwise, they automatically use the included free Barlow Condensed SemiBold and Medium fonts. Rendering works offline without installing fonts. TKC_FONT_DIR optionally selects a directory containing FRADMCN.TTF and FRAMDCN.TTF. The plotting smoke command saves lint results and returns a nonzero exit code if rendering or automated checks fail. Visual review is also required for final figures.

The commands above use the published archive. To rerun after more results arrive, prepare and validate a new named snapshot using the [data and scoring guide](docs/data-and-scoring.md), then pass its ID to both scripts. The current-partial snapshot contains preliminary recorded results. The ddhq-20261104-222052-est snapshot has documented House control derived from district calls. The synthetic-complete snapshot supplies invented software test data. For independent notebook execution, set CONGRESS_SCORECARD_SNAPSHOT before launching the notebook frontend.

Runs preserve earlier outputs under outputs/<snapshot>/<run-id>/. Each run records inputs, source code, dependencies, and graphics asset hashes. See the [data and scoring guide](docs/data-and-scoring.md) for schemas, interfaces, new snapshot preparation, and execution options.

## Publishing reviewed results

Execution preserves a new run under `outputs/`; it does not update the GitHub-facing notebook or published figures. Run the selected snapshot, review its results and every graphic, then promote that exact run:

```powershell
python scripts/run_notebooks.py --snapshot ddhq-20261104-222052-est
python scripts/publish_scorecard.py --run outputs/ddhq-20261104-222052-est/<run-id> --reviewed
```

Replace `<run-id>` with the successful runner's directory name. `--reviewed` confirms that you completed numerical and visual review; automated checks do not establish visual approval. Publication validates the run and promotes the selected executed notebook, PNGs, plotted-data CSVs, and portable provenance together. Synthetic runs cannot be published. See the [publication procedure](docs/data-and-scoring.md#publishing-a-reviewed-scorecard-run) for checks and recovery behavior.

The default publication target is the Congress scorecard. Pass `--part 02_forecast_accuracy` for forecast accuracy or `--part 03_kalshi_trading_volume` for trading volume. Each command promotes the selected notebook and its associated files.

## License

The project’s original software code is licensed under the [MIT License](LICENSE). Third-party data and source captures remain subject to their respective terms. The TKC logo and branding remain subject to their respective rights. Bundled Barlow Condensed fonts use the included [SIL Open Font License](src/congress_scorecard/assets/fonts/OFL.txt).
