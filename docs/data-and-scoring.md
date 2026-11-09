# Data and scoring foundation

Part 1 supplies the shared Python package, frozen-data audit, results snapshots, scoring interfaces, notebook execution and TKC plotting. Parts 2–4 implement the three analysis notebooks. All commands below run from the release root.

## Setup

Use Python 3.12. Create and activate a project environment in PowerShell.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[notebooks,plotting,audit,test]"
python scripts/validate_inputs.py --snapshot current-partial
python -m pytest -q
```

Use the editable installation because data and notebooks are release project files. The core package uses NumPy and pandas. The extras supply nbclient, nbformat and ipykernel for execution, openpyxl for the source audit, pytest for verification, and the TKC renderer's pinned plotting dependencies. No external kernelspec installation is required. The runner launches the active Python interpreter.

The original workbooks and captures are needed for the source audit. Snapshot validation and notebook execution use the files included in this project.

## Frozen forecasts and explicit transformations

The four original files in `data/input/` remain byte-for-byte preserved. Their SHA-256 values are stored in `data/provenance/frozen-inputs.json`. `sources.csv` retains the original workbook lineage. Original forecast headers, row order, source probabilities, shares, margins, volumes, dates and notes remain in the raw tables.

`load_inputs(snapshot=...)` returns an `Inputs` object.

| Field | Shape and meaning |
| --- | --- |
| `raw` | Dictionary of the four recorded CSV DataFrames plus selected canonical Senate and House results |
| `senate` | 35 rows indexed by unique `race_id`, including original forecast columns, prepared values and prefixed result metadata |
| `house` | One row indexed by `House`, including forecasts, prepared values and prefixed result metadata |
| `manifest` | Selected snapshot description, timestamps, synthetic label, exceptions and hashes |
| `diagnostics` | Counts, unresolved identifiers, metric eligibility and qualifications |
| `hashes` | Frozen and selected input/evidence hashes checked during loading |

The prepared Senate table adds the following columns.

- `p_kalshi`, `p_economist`, `p_votehub` are recorded Candidate A win probabilities.
- `p_kalshi_normalized` is A divided by A+B. It conditions on A or B winning and is a sensitivity.
- `p_model_mean` is the fixed equal-weight Economist/VoteHub mean. `p_blend` is half raw Kalshi and half that mean. VoteHub Complete incorporates Kalshi and expert ratings.
- `p_cook_primary`, `p_cook_senate`, `p_cook_wide` implement the three approved mappings. Primary Solid/Likely/Lean probabilities are .99/.97/.94. Senate values are .99/.978/.981. Wide values are .99/.90/.70. Toss-Ups are .50 and R-favored ratings reverse the probability for the recorded A orientation.
- `p_constant` assigns .95 to the Cook-favored side and .50 to Toss-Ups. `p_uniform` is .50.
- `share_economist`, `share_votehub`, `share_rcp`, `share_silver` are A/(A+B). Models have recorded fractional shares, while poll inputs and results use 0–100. Prepared shares use 0–1. Recorded margins are retained independently.
- `sample_all`, `sample_non_solid`, `sample_robust` preserve the frozen 35, 15 and 11 race memberships. Robustness includes endpoints .10 and .90 in the mean of raw Kalshi, Economist and VoteHub probabilities. `sample_cook_directional` identifies the 28 non-Toss-Ups.
- `volume` is the recorded Kalshi volume, with units unresolved.
- `result_*` carries the canonical results metadata. `y` is 1 for a verified Candidate A win, 0 for a verified Candidate B win, and missing otherwise.
- `call_eligible` and `share_eligible_<source>` control different metrics. `actual_share` can retain an interim topline even when it is ineligible for scoring.

Missing A or B shares produce a missing normalized share. A zero A+B denominator produces a missing result. Invalid scales and nonfinite values raise errors. No result-dependent filtering changes planned sample membership.

## Shared scoring API

Import public functions from `congress_scorecard`. Scalar transformation helpers return a float or a pandas Series. Scored aggregates return a `ScoreResult`.

| Function | Input and output |
| --- | --- |
| `cook_probability(rating, mapping="primary", a_party="Democratic")` | Directional Cook rating to A probability, with keyword options |
| `normalize_probabilities(a, b)` | Aligned probabilities to A/(A+B), permitting a recorded overround |
| `two_candidate_share(a, b, scale=1)` | Aligned shares to A/(A+B), with explicit recorded scale |
| `favorite(probability)` | Series of 1, 0 or missing, with exactly .50 abstaining |
| `select_sample(frame, sample="all")` | Forecast-defined subset, using `non_solid`, `robust` or `cook_directional` as alternatives |
| `match_sample(frame, columns, outcome="y", eligibility="call_eligible", weights=None)` | Common keyed rows, exclusions and weights. Options after columns are keyword arguments |
| `brier_loss(p, y)` | Per-race squared probability error on 0–1 scale |
| `log_loss(p, y, clip=True)` | Per-race natural-log loss. Clipped calculation uses [.01,.99] |
| `probability_score(frame, source, metric="brier", weights=None, clip=True)` | Weighted or equal-weight aggregate, with Brier or `log` metric |
| `paired_difference(frame, first, second, metric="brier", weights=None, clip=True)` | First source loss minus second on identical eligible rows and weights |
| `brier_skill(frame, source, reference, weights=None)` | 1 minus source Brier divided by reference Brier on the same sample |
| `calls_correct(frame, source)` | Correct calls, calls made, abstentions and accuracy among eligible resolved races |
| `vote_share_score(frame, source, metric="mae", peers=(), weights=None)` | MAE, bias or RMSE in fractional-share units. Peers enforce shared coverage and compatibility |
| `expected_wins(frame, source)` | Full-field forecast plus expected/actual counts on matched eligible races |
| `house_expected_seats(row, method="directional")` | Cook House expected seats with directional, symmetric, tossup_half or deterministic method |
| `house_control(inputs, source, metric="brier", clip=True)` | Gated House probability score. Source `cook` returns hit/miss calls only |
| `house_seat_error(inputs, source, cook_method="directional")` | Gated final Democratic seat error for cook, economist or votehub |
| `senate_caucus_seats(inputs, source, holdover=None, scenario="primary")` | Explicit unavailable result until caucus methodology is approved. Scenarios accept each independent race identifier |

Function signatures mark options as keyword-only where applicable. The table abbreviates this syntax for readability. Use prepared column names, such as `p_kalshi`, for probability-score source arguments. House seat source names are lowercase labels. Cook expected seats evaluate to 229.3764, 230.60, 229.7724 and 231 under the four methods.

`ScoreResult.summary()` returns value, status, planned/eligible counts, eligible race identifiers, per-race exclusion reasons, weighting flag, eligible original weight sum and qualifications. `per_race` retains the selected rows, normalized `_weight` and the relevant losses/errors. `status` is `ok`, `qualified` or `unavailable`. Preserve qualifications when publishing tables and charts.

Empty scoring samples return unavailable values. Exact .50 forecasts remain eligible observations for probability loss but make no directional call. Zero reference Brier produces an unavailable skill score. Unclipped log loss preserves infinity. An infinity-minus-infinity paired contrast or an aggregate with opposing infinite losses is explicitly unavailable. Undefined differences on zero-weight rows do not affect the aggregate. Zero-weight observations contribute nothing even if their loss is infinite.

Weights must be finite and nonnegative. Missing weights exclude rows. All-zero eligible weights raise an error. Weights are normalized after common eligibility selection, and both sides of a contrast use those same weights. Equal weighting uses 1/n. Duplicate race identifiers and missing required columns raise errors. Forecast and result joins are keyed, with exact frozen-field coverage and candidate orientation validation.

Examples use keyword options as implemented.

```python
from congress_scorecard import (
    load_inputs, select_sample, probability_score, paired_difference,
    brier_skill, calls_correct, expected_wins, vote_share_score,
    house_control, house_seat_error,
)

data = load_inputs(snapshot="current-partial")
primary = select_sample(data.senate, "non_solid")
contrast = paired_difference(primary, "p_kalshi", "p_model_mean")
print(contrast.summary())                  # 15 planned, 13 eligible
print(contrast.per_race[["loss_first", "loss_second", "difference"]])

raw = probability_score(primary, "p_kalshi", metric="log", clip=False)
clipped = probability_score(primary, "p_kalshi", metric="log")
skill = brier_skill(primary, "p_kalshi", "p_cook_primary", weights="volume")
calls = calls_correct(data.senate, "p_kalshi")
counts = expected_wins(data.senate, "p_kalshi")
polls = vote_share_score(data.senate, "share_rcp", peers=["share_silver"])
house = house_control(data, "p_kalshi")
final_seats = house_seat_error(data, "economist")
```

Bootstrap, sign-flip, copula diagnostics and their interpretation belong to Part 3's notebook implementation. It should reuse the matched per-race rows, retain the plan's seeds/counts, and report unavailable diagnostics when their prerequisites fail.

## Results snapshots and validation

The release provides three explicit selections.

| Snapshot | Senate | House | Purpose |
| --- | --- | --- | --- |
| `current-partial` | November 4 at 22:05 Eastern, 33 verified calls | Frozen November 6 at 20:25 Eastern, 254 D / 161 R / 20 undecided | Preserve current recorded inputs |
| `ddhq-20261104-222052-est` | Same November 4 Senate capture | November 4 at 22:20 Eastern, 247 D / 152 R / 36 undecided | Evidence-backed threshold control |
| `synthetic-complete` | 35 invented complete outcomes | Invented 240 D / 195 R final seats | Software fixture, always labeled synthetic |

The current House row lacks a matching capture for its later counts, so its control remains unverified for scoring. The separate archived snapshot supports Democratic control under the approved 218-seat threshold rule. Both real snapshots withhold final House seat error and national-vote scoring.

Place future results in a new `data/results/<dated-id>/` directory. Use a descriptive identifier such as `ddhq-YYYYMMDD-HHMMSS-est` with the actual capture date. Each directory contains `senate_results.csv`, `house_results.csv` and `manifest.json`. Preserve previous snapshots. The bootstrap script is a one-time reconstruction tool and refuses to overwrite existing initial snapshot directories.

Canonical schemas are also exported as `SENATE_COLUMNS` and `HOUSE_COLUMNS` from `congress_scorecard.data`. CSV boolean fields accept lowercase or uppercase true/false and blank. Numeric blanks and unavailable metadata stay missing. All canonical timestamps require timezone offsets. Result percentages use 0–100.

| Senate fields | Contract |
| --- | --- |
| `race_id,candidate_a,candidate_b` | Exactly the 35 forecast identifiers and their recorded candidate orientation |
| `winner` | Recorded A or B name, or blank. Never inferred from vote shares |
| `call_status` | called, pending or unverified |
| `call_source,call_timestamp,call_verified,call_evidence` | Verified calls require DDHQ, timestamp and release-relative JSON evidence |
| `recount_status` | Blank/unknown, none, active or completed. Active recounts are excluded |
| `percent_reporting,reporting_type` | Recorded reporting estimate and its meaning |
| `a_share,b_share,other_share,round_used` | Recorded 0–100 shares and actual round/topline description |
| `vote_complete,vote_evidence` | Explicit completeness assessment and release-relative supporting evidence |
| `share_compatible_economist,share_compatible_votehub,share_compatible_rcp,share_compatible_silver` | Source-specific documented target compatibility. A true value requires completeness evidence |
| `snapshot_timestamp` | Component capture timestamp, matching manifest senate_timestamp |

A Senate call-evidence JSON has a `rows` list, following the preserved DDHQ provenance shape. Each row has `raceId`, `winner`, `candidateAId`, `candidateBId`, `calledCandidateIds` and `callTimes`. A call-time entry has `cand_id` and `called_time`. The loader verifies winner, called candidate ID and timestamp agreement. Real evidence must not be marked synthetic. Supporting vote evidence must describe completeness and the source's forecast target/round. Explicit compatibility judgments are documented assertions that require review of the cited evidence.

| House fields | Contract |
| --- | --- |
| `race_id` | House |
| `dem_seats,gop_seats,undecided_seats` | Nonnegative integers totaling 435 when all are present |
| `control` | Democratic, Republican or blank |
| `control_source,control_timestamp,control_verified,control_evidence,control_method` | DDHQ evidence for district_threshold or chamber_projection |
| `seats_final,seats_evidence` | Finality requires zero unresolved seats, complete counts and evidence |
| `dem_share,gop_share` | Recorded reported national shares on 0–100 scale |
| `vote_complete,vote_evidence,vote_compatible` | Separate documented national-vote completeness and comparability |
| `snapshot_timestamp` | Component capture timestamp, matching manifest house_timestamp |

Threshold evidence follows the archived House provenance shape. It includes `retrievedAtEastern`, `calledSeatsByParty`, and 435 unique `races` with `raceId`, `winnerParty` and `calledCandidateIds`. Counted district calls must reconcile to the selected snapshot's party counts and establish at least 218 seats for the control party. Evidence and selected House component timestamps must agree. Projection evidence instead contains `source="DDHQ"` and `projectedControl`. Final-seat and national-vote evidence require separate source review.

A manifest contains `schema_version=1`, `snapshot_id`, `synthetic`, `description`, `senate_timestamp`, `house_timestamp`, `qualifications`, `approved_exceptions`, and `hashes`. Start from a supplied manifest to retain the recorded unresolved-methodology fields. Use release-relative paths in `hashes`, including both result CSVs and every referenced evidence file. Paths outside the release root are rejected.

After saving a new snapshot and its evidence, compute hashes with the shared helper.

```python
import json
from pathlib import Path
from congress_scorecard.data import sha256

root = Path.cwd()
snapshot = "ddhq-YYYYMMDD-HHMMSS-est"  # replace with actual capture identifier
directory = root / "data/results" / snapshot
manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
paths = [
    f"data/results/{snapshot}/senate_results.csv",
    f"data/results/{snapshot}/house_results.csv",
    f"data/results/{snapshot}/evidence.json",  # include every cited evidence file
]
manifest["hashes"] = {relative: sha256(root / relative) for relative in paths}
(directory / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
```

Validate before executing.

```powershell
python scripts/validate_inputs.py --snapshot ddhq-YYYYMMDD-HHMMSS-est
```

Validation checks frozen hashes, selected hashes, schemas, IDs, orientation, numeric ranges, timestamps, calls and evidence, vote eligibility metadata, and House reconciliation/finality. Incomplete evidence produces explicit omissions or validation errors. Replacing a frozen forecast or substantively changing scoring rules still requires approval.

## Running all notebooks or one notebook

One command executes all three notebooks with fresh kernels and regenerates outputs using the selected snapshot.

```powershell
python scripts/run_notebooks.py --snapshot current-partial
```

A run is written to `outputs/<snapshot-id>/<UTC-run-id>/`. The run identifier includes UTC time and a unique suffix. The output tree contains executed `notebooks/`, per-part `figures/` and `tables/`, cell and kernel `logs/`, and `run.json`. New runs preserve earlier directories. `--output-root` selects an explicit alternate parent.

The runner validates before starting kernels. Each notebook runs in a fresh kernel with the current Python interpreter and release root as its working directory. Failures produce a nonzero exit code. Executed cells, the failed notebook, kernel logs and a traceback remain available. The run manifest records source/input/notebook hashes, exact snapshot metadata, dependency versions, Python interpreter, coverage and execution state. No analysis cells are added to the source notebooks.

Each implemented notebook should begin with the same shared context mechanism.

```python
from congress_scorecard import load_context

ctx = load_context("01_congress_scorecard")
data = ctx.inputs
print(data.diagnostics)
# Save per-part outputs only through these explicit destinations.
table_path = ctx.tables_dir / "summary.csv"
figure_directory = ctx.figures_dir
```

Use `02_forecast_accuracy` and `03_kalshi_trading_volume` for the other notebook identifiers. In an independent session select a snapshot before executing cells.

```powershell
$env:CONGRESS_SCORECARD_SNAPSHOT = "current-partial"
```

A notebook frontend can use the installed environment as its kernel. Set the environment variable in the process launching that frontend, or pass `snapshot="current-partial"` to `load_context` for an explicit standalone selection. An unset selection raises an error.

The batch runner supplies both `CONGRESS_SCORECARD_SNAPSHOT` and `CONGRESS_SCORECARD_OUTPUT_DIR`. Without a supplied output directory, independent context loading creates a unique run directory. To share a chosen directory among independently run notebooks, set the output variable to its absolute path. The context rejects directories whose manifest names different snapshot inputs.

Reproduce an earlier run by restoring the source and dependency versions recorded in its `run.json`, retaining the original snapshot/evidence hashes, and running the same snapshot command. With the same code and snapshot, repeated runs keep their data selection while creating new output directories. Statistical notebooks must use the analysis plan's fixed seeds.

The exact integration checks after Parts 2–4 land are:

```powershell
python scripts/validate_inputs.py --snapshot current-partial
python scripts/run_notebooks.py --snapshot current-partial
python scripts/validate_inputs.py --snapshot synthetic-complete
python scripts/run_notebooks.py --snapshot synthetic-complete
```

Confirm all notebook records succeeded, `code_cells` is positive for each notebook, and generated tables/figures contain the chosen snapshot label and coverage. Notebook outlines have zero code cells and are marked `outline_only` with run-level `integration_status="outlines_only"`. Their execution verifies the runner. The tests separately execute notebooks that import the shared context, switch snapshots, export coverage and prove kernel isolation.

## Publishing a reviewed scorecard run

`python scripts/run_notebooks.py --snapshot <snapshot>` creates a fresh run and prints its output directory. It never replaces the release notebook or `figures/01_congress_scorecard/`. Keep the desired run directory; do not combine artifacts from different runs.

Before publication, reconcile headlines, rankings, exclusions, and plotted marks against the exported rows. Inspect every graphic at native, intended display, and thumbnail sizes, and confirm chart lint passed. Review qualifications, snapshot identifiers, chamber timestamps, and preliminary-result gates. Both approved font configurations have automated rendering checks; visual review remains a separate human or agent task.

```powershell
python scripts/publish_scorecard.py --run outputs/ddhq-20261104-222052-est/<run-id> --reviewed
```

The command requires an explicit numerical-and-visual-review attestation. It accepts only successful non-synthetic runs with an executed scorecard notebook matching the current notebook source. It checks the snapshot manifest, current input and source hashes, error-free executed cells, timestamps, chart lint records, PNG dimensions, CSV snapshot labels, and exact PNG/CSV hashes recorded in the run's `analysis-provenance.json`. Changed code or inputs require a fresh execution and review. The command does not independently establish scientific correctness or visual approval.

Validation completes before publication changes. Replacements and backups are staged in the parent workspace's `_scratch/part-2/`. A replacement failure restores the prior managed files; the command returns a nonzero exit code. A successful promotion updates the executed notebook and the selected run's listed PNGs, CSVs, and `provenance.json`. Only superseded artifacts listed in the previous publication manifest are removed. Unlisted files and historical run directories remain intact. Publication provenance records the run identifier, review attestation, snapshot, inputs, source code, dependencies, brand assets, and final artifact hashes without local machine paths.

An existing run without artifact hashes predates this procedure: rerun and review it rather than publishing it. Current-partial may be promoted after review with its own coverage and withheld-control labels; the dated archive remains the selected release until an explicit promotion changes it. Synthetic-complete remains verification-only.

## TKC plotting

The project provides a Matplotlib canvas, consistent source and party colors, direct-label bars, and PNG exports. Use the canvas axes for other chart forms.

The renderer prefers Franklin Gothic Demi Condensed and Franklin Gothic Medium Condensed. TKC_FONT_DIR optionally supplies local FRADMCN.TTF and FRAMDCN.TTF files. If a role has no local or installed Franklin Gothic font, it uses the bundled Barlow Condensed SemiBold for headlines and emphasis or Medium for supporting text. Each role resolves independently, so partial font installations work. The free fallback fonts and their SIL Open Font License are included with the package and require no runtime download. Run provenance records the selected family, filename, hash, and fallback status. The logo is included with the package.

Generic canvas axes use TKC v2 typography with Franklin Gothic Medium Condensed supporting ticks at 28px, light-blue labels and no tick marks. Axis titles use Franklin Gothic Demi Condensed at 34px in white. Sizes scale from a 1080px short edge. Scientific-notation offsets use the supporting font. Chart-specific spines and gridlines can be configured on the returned axes.

The default canvas is 1920×1080 with a medium logo at 10% of the shorter edge. Other formats are square, portrait, and portrait_9x16. Logo presets are small at 7.5%, medium at 10%, and large at 12.5%. Colors use navy #0B165A, light blue #80C2FC, pale gold #EEEAAC, and white. Source colors are consistent across notebooks. Use direct labels alongside color.

~~~python
from congress_scorecard.plotting import make_canvas, bar_chart, save_chart, source_colors

colors = source_colors()
canvas = make_canvas(
    "A supported headline from the selected data",
    subtitle=f"Results snapshot {data.snapshot_id}. State eligible counts here.",
    source="Source: Recorded forecasts and verified DDHQ calls. Preliminary.",
)
bar_chart(canvas, labels, values,
          colors={label: colors[key] for label, key in label_to_source.items()})
paths = save_chart(canvas, "score-comparison", out_dir=ctx.figures_dir,
                   scratch_dir=part_scratch_directory)
~~~

The notebook is the editable source for its figures. For standalone chart scripts, pass script=__file__ to save a copy beside the PNG. Always supply an output directory.

Run python scripts/render_smoke.py to create an illustrative chart under outputs/plotting-check/. Inspect the native image, destination-size preview, and thumbnail. Verify marks against the computed values, text and logo bounds, safe areas, source notes, and readability. Review every final chart in its intended format. The smoke command writes lint.json with image, text-bound, collision, and logo checks. Rendering or lint failures return a nonzero exit code. Run manifests record SHA-256 hashes of the resolved fonts and packaged logo using filenames without machine paths.

## Data decisions, open issues and verification

The machine-readable issue register is `data/provenance/issues.json`. Current decisions and omissions are:

- DDHQ determines binary outcomes under the current plan. The older AP wording in import provenance is historical.
- A vote lead never becomes a call. AK-SEN and MS-SEN remain pending. Current primary paired scoring uses 13 of the 15 planned non-Solid races.
- Reporting estimates are separate from completeness. All current primary share comparisons are unavailable. AK-SEN and ME-SEN also lack documented ranked-choice target compatibility.
- The approved House district-threshold exception can score the dated November 4 archive. The later frozen November 6 row lacks matching evidence. Final seat error and national-vote comparisons remain gated.
- Known active recounts are deferred. Archived recount status remains unknown.
- Rule 10's independent coding is retained as an unresolved methodology assumption, and caucus seats/control stay unavailable. No holdover constant or control tie convention has been invented. A campaign release contradicts Democratic-caucus coding for Osborn, Bodnar and Bengs. [Campaign statement](https://www.sethformontana.com/news/independent-candidates-seth-bodnar-dan-osborn-and-brian-bengs-put-the-caucus-question-to-rest)
- Kalshi probability scoring is provisionally approved despite missing original price-measure and contract verification. KY-SEN links to a Louisiana-named URL, with a frozen note saying confirmed as entered. The issue is propagated through score qualifications.
- The project owner confirmed the frozen Kalshi volume column is in U.S. dollars on November 9, 2026. The trading-volume notebook uses those units for currency labels and its under-$250,000 cutoff. Historical snapshot manifests retain their original unit status. Current API field definitions cannot establish which field was manually captured previously. [Kalshi market API](https://docs.kalshi.com/api-reference/market/get-market)
- Source-specific forecast publication times, retrieval timezone, captures and Economist model-update metadata are unavailable. Recorded row timestamps remain intact. VoteHub Complete is market-informed and no Legacy forecasts were collected.

The frozen audit command requires the original parent-workspace artifacts.

```powershell
python scripts/audit_inputs.py
# If the release has moved, provide the parent containing data/ and .planning/.
python scripts/audit_inputs.py --workspace "absolute-path-to-original-parent"
```

The audit reconciles all four CSVs with the hashed working workbook, compares the two forecast tabs with the original workbook, checks archived DDHQ call identifiers/timestamps and shares, and validates all three adapters.

Verification covers scoring and data validation, snapshot switching, fresh notebook kernels, preserved run directories, and expected execution failures. The three analysis notebooks are implemented. The synthetic snapshot supplies software test data.

## Forecast-accuracy execution and publication

Notebook 02 uses `load_context("02_forecast_accuracy")` and the same explicit snapshot and preserved-run mechanism. It keeps the 35/15/11 forecast-defined samples separate from scoring eligibility. All contrasts use paired eligible races and equal weights; vote-share eligibility is separate. The primary-only sign-flip analysis enumerates nonzero-pair signs, assuming independent symmetric differences. Paired bootstrap sensitivities use 10,000 replicates and seed 20261104. Calibration and model-conditional power use 20,000 draws, seed 20261105, and latent Gaussian correlations 0, 0.1, 0.25, and 0.5. This parameter is not binary outcome correlation. Numerical helper definitions remain in tagged notebook cells and require no additional dependency.

Each run stores numerical tables under `tables/02_forecast_accuracy/` and PNGs under `figures/02_forecast_accuracy/`. Plotted CSVs identify the snapshot and synthetic status. The notebook contains the editable chart source and executed numerical tables. Real vote-share results are unavailable until a new validated snapshot supplies completeness and source-specific target compatibility. Synthetic complete execution verifies that branch without supplying election findings.

The publisher accepts `--part 01_congress_scorecard` (default), `--part 02_forecast_accuracy`, or `--part 03_kalshi_trading_volume`. Python entry points `prepare_publication(root, run, *, part="01_congress_scorecard")` and `publish(root, run, *, reviewed=False, part="01_congress_scorecard")` accept the same selection. Validation and promotion operate only on that part. Numerical and visual review is required before `--reviewed`; synthetic runs remain unpublishable. Historical provenance for the other part continues to describe its original run and is not rewritten when shared code changes.

Forecast-accuracy graphics use VoteHub as the display name; the captured version remains Complete and its Kalshi inputs remain disclosed. Greek ρ is drawn as a standalone symbol with Matplotlib's bundled DejaVu Sans, while surrounding text retains the selected Franklin Gothic or Barlow font. The exact symbol-font filename, SHA-256, character, and role are recorded in analysis and publication provenance. Lint permits only that standalone character from the resolved bundled font, and publication validates its metadata. No font download or additional dependency is required.

```powershell
python scripts/run_notebooks.py --snapshot ddhq-20261104-222052-est
python scripts/publish_scorecard.py --run outputs/ddhq-20261104-222052-est/<run-id> --part 02_forecast_accuracy --reviewed
```

## Senate caucus follow-up

`senate_caucus_seats` intentionally remains unavailable. Resolving all 35 race winners updates Candidate A winner scoring but cannot unlock caucus seat totals or Senate control. A separate approved methodology and implementation must establish:

- Evidence-backed caucus coding for each independent candidate and treatment of conflicting or absent statements, including the rule 10 sensitivity scenarios.
- The Democratic-caucus composition of holdover seats, with dated supporting evidence.
- Treatment of unresolved and recount-affected races in forecast totals, partial actual totals, and final seat errors.
- The control threshold and tie-breaking convention, plus the evidence gate for an actual control outcome. Expected seat sums are not control probabilities; those require a published chamber forecast or an approved joint outcome model.

The issue register's caucus entry remains open. No caucus rules, evidence, or chamber calculations change as part of the publication workflow.
