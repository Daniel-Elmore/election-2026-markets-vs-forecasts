# Analysis data

These CSVs are direct extracts from the four tabs of the working workbook named in the [extract manifest](provenance/sources.csv). The forecast tabs also match the original scorecard workbook. Forecasts reflect the November 2, 2026 snapshot. Results come from separate preliminary snapshots.

| File | Workbook tab | Records | Contents |
| --- | --- | ---: | --- |
| [Senate forecasts](input/senate_forecasts.csv) | Predictions | 35 | Candidates, Cook ratings, poll averages, forecast probabilities and shares, and Kalshi volume and contract URLs |
| [House forecasts](input/house_forecasts.csv) | HousePredictions | 1 | Chamber control forecasts, projected seats, Cook rating counts, and generic-ballot inputs |
| [Senate results](input/senate_results.csv) | Results | 35 | Candidates, recorded winners, estimated vote reporting, and reported vote shares and margins |
| [House results](input/house_results.csv) | HouseResults | 1 | Reported national vote shares, called and undecided seats, and control derived from called seats |

The CSVs preserve the workbook's headers, row order, values, and units. Formula cells contain their saved values. Empty cells are blank fields. Dates and timestamps use ISO 8601 and preserve the workbook's clock time. Probability and vote-share fields retain their original scales. Kalshi volume units still need source verification.

## Results status

- The Senate results use DDHQ at 10:05 p.m. Eastern on November 4. Two rows have blank winner fields.
- The House row is marked November 6 at 8:25 p.m. Eastern, later than the November 4 date in the workbook filename and the archived November 4 House capture. The workbook notes partial vote reporting, unresolved runoffs, and chamber control derived from DDHQ-called district winners.
- Rule 8 of the [analysis plan](../docs/analysis-plan.md) uses DDHQ calls. In these extracts, a blank Senate winner is pending and excluded from outcome-based scores. Final seat counts, per-race call metadata, and comparable vote shares are separate validation steps.

The [extract manifest](provenance/sources.csv) records workbook lineage and snapshot metadata. The underlying workbooks and available source captures are in the parent workspace.
