# Analysis data

These CSVs are direct extracts from the four tabs of the working workbook named in the [extract manifest](provenance/sources.csv). The forecast tabs also match the original scorecard workbook. Forecasts reflect the November 2, 2026 snapshot. Results come from separate preliminary snapshots.

| File | Workbook tab | Records | Contents |
| --- | --- | ---: | --- |
| [Senate forecasts](input/senate_forecasts.csv) | Predictions | 35 | Candidates, Cook ratings, poll averages, forecast probabilities and shares, and Kalshi volume and contract URLs |
| [House forecasts](input/house_forecasts.csv) | HousePredictions | 1 | Chamber control forecasts, projected seats, Cook rating counts, and generic-ballot inputs |
| [Senate results](input/senate_results.csv) | Results | 35 | Candidates, recorded winners, estimated vote reporting, and reported vote shares and margins |
| [House results](input/house_results.csv) | HouseResults | 1 | Reported national vote shares, called and undecided seats, and control derived from called seats |

The CSVs preserve the workbook's headers, row order, values, and units. Formula cells contain their saved values. Empty cells are blank fields. Dates and timestamps use ISO 8601 and preserve the workbook's clock time. Probability and vote-share fields retain their original scales. The project owner confirmed on November 9, 2026 that the frozen Kalshi volume column is in U.S. dollars. The original source field remains unidentified.

## Latest results update

The selected release uses `results/ddhq-20261112-manual/`. Only MS-SEN and the House were refreshed; the other 34 Senate rows retain November 4 data. The four original `input/` CSVs and prior snapshots remain unchanged.

- DDHQ called Scott Colom on November 11 at 6:28 p.m. EST. November 12 at 12:24 p.m. figures show 474,178 Colom / 468,840 Hyde-Smith / 20,260 Pinkins, with >95% reporting. The canonical shares retain displayed 49.23 / 48.67 / 2.10 percentages. The numeric reporting field is blank because the source supplies a bound, not an exact percentage.
- Senate call coverage is 34/35; AK-SEN remains pending. Primary paired coverage is 14/15.
- DDHQ House counts observed November 12 are 255 D / 168 R / 12 undecided. An explicit DDHQ chamber projection establishes Democratic control. RCP displays 55.9% D / 42.7% R at 93% reporting. Neither final House seat error nor national vote scoring is eligible.
- New evidence is manually transcribed from public pages, checked against the supplied data, and hashed in the snapshot manifest. No API was used. See `provenance/manual-results-20261112.json`, `provenance/ddhq-ms-senate-call-20261112.json`, and `provenance/ddhq-house-projection-20261112.json`.

## Original extract results status

- The Senate results use DDHQ at 10:05 p.m. Eastern on November 4. Two rows have blank winner fields.
- The House row is marked November 6 at 8:25 p.m. Eastern, later than the November 4 date in the workbook filename and the archived November 4 House capture. The workbook notes partial vote reporting, unresolved runoffs, and chamber control derived from DDHQ-called district winners.
- Rule 8 of the [analysis plan](../docs/analysis-plan.md) uses DDHQ calls. In these extracts, a blank Senate winner is pending and excluded from outcome-based scores. Final seat counts, per-race call metadata, and comparable vote shares are separate validation steps.

The [extract manifest](provenance/sources.csv) records workbook lineage and snapshot metadata. The underlying workbooks and available source captures are in the parent workspace.
