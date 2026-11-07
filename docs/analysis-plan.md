# Election Night 2026: Forecasters vs. Markets

## Scope

- Congress only: 35 Senate races (33 Class II plus the OH and FL specials) and the House at chamber level.
- The series centers on prediction markets. The analysis ships in two parts: a general-audience piece and a statistics write-up for a portfolio.
- Subsets are derived from Cook ratings and a source-neutral rule at analysis time.
- All data is the Nov 2 snapshot, the day before the election.
- Candidate A is the first listed candidate: the Democrat, or the independent in NE, MT, ID and SD. Independents are coded as Democratic-caucusing (rule 10).

## Data Dimensions

| Source | Type | Senate | House (chamber) | Scored as |
|---|---|---|---|---|
| Kalshi | Market | A/B win probability, total volume (units to verify) | Control probability, total volume (units to verify) | Probability |
| The Economist | Forecaster | A/B win probability, projected shares | Control probability, seats | Probability, two-candidate share |
| VoteHub (Complete) | Forecaster, market-informed | A/B win probability, projected shares | Control probability, seats | Probability, two-candidate share |
| Cook Political Report | Forecaster | Rating per race | Seat counts by rating | Mapped probability (Senate), mapped seat count and hit/miss control call (House) |
| RCP average | Polling baseline | A/B vote share (partial coverage) | Generic ballot | Two-candidate share |
| Silver Bulletin weighted average | Polling baseline | A/B vote share (partial coverage) | Generic ballot | Two-candidate share |

Kalshi is the only market, selected for its trading volume. Silver Bulletin's average is weighted, which gives a second polling baseline alongside RCP's. Silver covers the largest share of competitive Senate races; RCP has gaps (for example NE-SEN). RCP is missing for 17 races and Silver for 11. A source with no data for a race is left out of that race's scoring, and poll-versus-poll comparisons use only the races both sources cover.

## How the Forecasts Are Constructed

**The Economist.** The forecast runs 25,001 simulated elections. It combines national and race-level polling (FiftyPlusOne) with fundamentals and nominee information, simulates national environments for the House popular vote, and adds uncertainty for how Senate races as a group differ from the House, so outcomes move together across races ([The Economist's model page](https://www.economist.com/interactive/2026/us-midterms/prediction-model/house)). Its published introduction describes inputs of primaries, polls, fundraising data, special election results and presidential approval, and does not list prediction markets or expert ratings as inputs. Candidate win probabilities are the share of simulations each candidate wins. The simulations represent modeled uncertainty and are not additional observed elections ([The Economist's forecast introduction](https://theeconomistoffthecharts.substack.com/p/our-prediction-model-for-americas)).

**VoteHub Complete.** The recorded VoteHub forecasts use the Complete version, which combines fundamentals and polling with expert ratings (Cook Political Report, Inside Elections and Sabato's Crystal Ball) and Kalshi order-book data. Market influence varies by race. It is larger in close races and where polling is sparse, differs by office, and is capped below 1, so it is not a fixed percentage weight. Liquid contracts rely more on last-trade prices and thinner markets more on bid-ask midpoints ([VoteHub methodology, sections 2.4 to 2.8](https://votehub.com/wp-content/uploads/2026/05/2026_votehub_midterm_methodology.pdf)). VoteHub also publishes a Legacy version built from fundamentals and polling only. No Legacy forecasts were collected, and this analysis does not compare Complete with Legacy or reconstruct a Legacy forecast.

**Interpretation.** VoteHub Complete is a market-informed forecasting system, not an independent, market-free benchmark. Kalshi versus VoteHub Complete asks whether the combined system scored better than Kalshi alone in this election. It cannot isolate the contribution of Kalshi, the expert ratings or the other inputs. Because Cook is also an input, Cook versus VoteHub Complete is not an independent comparison either. The Economist/VoteHub average is a mixed benchmark with indirect Kalshi and Cook exposure, and agreement between Kalshi and that average is not independent confirmation.

## Pre-Specified Rules

These rules were written after the election and are locked before any result is entered. They are pre-specified before scoring, not before outcomes were known. The plan is time-stamped or committed before the Results tabs are filled.

### Cook hit rates

Hit rates are computed from the counts on Cook's published accuracy page ([source](https://www.cookpolitical.com/analysis/national/cpr-archives/how-accurate-are-cook-political-reports-race-ratings)). Races won by or rated in favor of independents are excluded from those counts. A hit means the favored party won.

| Rating | All races | Senate | House |
|---|---|---|---|
| Solid | 7,128 / 7,130 = 99.97% | 325 / 325 = 100% | 6,437 / 6,439 = 99.97% |
| Likely | 1,098 / 1,131 = 97.1% | 91 / 93 = 97.8% | 857 / 884 = 96.9% |
| Lean | 914 / 975 = 93.7% | 101 / 103 = 98.1% | 629 / 678 = 92.8% |
| Toss Up (Democratic win share) | 537 / 1,116 = 48.1% | 86 / 165 = 52.1% | 329 / 688 = 47.8% |

House hit rates by direction: Likely D 424 / 441 = 96.1%, Likely R 433 / 443 = 97.7%, Lean D 321 / 354 = 90.7%, Lean R 308 / 324 = 95.1%.

### Rules

1. **Cook mapping, primary (all-race pooled).** Solid 0.99, Likely 0.97, Lean 0.94, Toss-Up 0.50. Solid is capped at 0.99 (observed 99.97%) as a conservative modeling choice that limits the log loss from a single upset; the uncapped rate already gives finite log loss. Toss-Up 0.50 is an assumption, close to the observed Democratic share. Map to the probability that candidate A wins: for a rating favoring B, A gets 1 minus the mapped value. Toss-Up carries no directional call and is excluded from hit-rate counts.
2. **Cook mapping, Senate-only.** Solid 0.99, Likely 0.978, Lean 0.981, Toss-Up 0.50. Senate buckets are small (93 Likely, 103 Lean races) and misses cluster in wave years.
3. **Cook mapping, wide sensitivity.** Solid 0.99, Likely 0.90, Lean 0.70, Toss-Up 0.50. Report all three mappings. If Cook's rank changes between mappings, say so.
4. **Scoring conventions.** Brier score is the mean over races of (p - y)^2 on the 0 to 1 scale, where p is the probability that A wins and y is 1 if A wins and 0 otherwise. Log loss is the mean of -[y ln p + (1 - y) ln(1 - p)] with natural logs. Brier uses the analysis probabilities defined for each source, without clipping: Kalshi uses the raw published A probabilities in the primary analysis and the rule 5 A/B-normalized probabilities in the sensitivity analysis, the Economist and VoteHub use their published A probabilities, and Cook uses its mapped values. Log loss is reported with analysis probabilities clipped to [0.01, 0.99] and, where finite, with unclipped analysis probabilities. A paired difference is the loss of the first-named source minus the loss of the second, so a positive value means the first-named source scored worse. Each skill score is computed on exactly the same races and weights as its reference. The Economist sits at 0.01 or 0.99 in 18 races and VoteHub in 17, so those sources tie Cook on most Solid races.
5. **Kalshi probabilities.** Primary: the raw published A probability scored against the A win indicator. This is the unconditional probability that A wins, the same target as the Economist and VoteHub A probabilities and as the expected-seat sums in rule 10. Sensitivity (A/B normalization assumption): normalize A and B to A / (A + B), which conditions on A or B winning. A and B prices sum to slightly more than 1 in only two races (AK-SEN 1.010, ID-SEN 1.004), and price sums near 1 do not show that other candidates' win probabilities are negligible. Report whether normalization changes any substantive conclusion. Before scoring, confirm for each contract the price measure recorded (last trade, midpoint or other) and the outcomes the contract covers. The same policy applies to House control probabilities (the Kalshi Democratic and Republican prices sum to 0.999).
6. **Orientation.** Candidate A is the first listed candidate. All probabilities refer to A winning.
7. **Two-candidate share.** Published vote shares are preserved as recorded, including third-party and undecided shares. For comparisons, convert to A / (A + B) and label the result "two-candidate share", because A is an independent in four races. Each source's published quantity is checked first: the Economist and VoteHub shares already sum to 1 except for MT-SEN (VoteHub sums to 0.901) and ID-SEN (VoteHub sums to 0.999), while RCP and Silver include undecideds. Actual results are converted the same way.
8. **Resolution.** The winner called by Decision Desk HQ (DDHQ) determines the binary outcome. The vote-share leader does not determine the winner automatically. For every race the Results tab records call status, call source, call timestamp, recount status and, for ranked-choice races (for example ME-SEN and AK-SEN where applicable), the round used. Probability forecasts are scored when a race is called. Vote-share forecasts are scored once comparable results are sufficiently complete, using the round that matches the source's forecast target. When a source's ranked-choice target is unclear, that forecast is flagged and excluded from the primary comparable-share analysis. Mark uncalled races as pending and exclude them from both the numerator and denominator of outcome-based scores until DDHQ calls them. Label interim scores preliminary, report the number of eligible races, and use the same called races for paired comparisons. Flag recounts and score them last. Score chamber control once DDHQ projects it, and score final seat totals when the remaining races are resolved.
9. **Snapshot and provenance.** Scores reflect the Nov 2 values as recorded, not closing prices. For every source the record holds a dated capture or saved extract, the source's publication time, the retrieval time with timezone, the source version, and the candidate or contract identifier. The VoteHub version is recorded as Complete, and Legacy forecasts are unavailable. The Economist model version or update date shown at capture is also recorded. Unequal timing across sources and rows can affect comparisons in either direction.
10. **Senate seats, control and caucus coding.** Whether A wins each race is defined for all 35 races and does not depend on caucus status, so a missing caucus statement never delays scoring a race outcome. Democratic-caucus seat totals and control do depend on it. Expected Democratic-caucus seats are the sum of the analysis probabilities for races whose A candidate is coded Democratic-caucusing, plus Democratic-caucus holdover seats not up in 2026, entered as a constant before scoring. Actual seats are counted the same way. Report signed and absolute seat error for each source. Summing race probabilities gives expected seats without an independence assumption. It does not give a control probability, which needs a joint outcome model or a published chamber forecast, and expected seats alone do not determine which party is more likely to control. Published control probabilities are scored separately against the binary control outcome. Any control call inferred from expected seats uses the threshold implied by the tie rule (ties resolve to the party of the Vice President) and is labeled an analyst-derived heuristic. The four independents (Osborn, Bodnar, Achilles, Bengs) are coded Democratic-caucusing in the primary calculation, and a cited public statement supporting each assumption is documented before the seat and control analysis. Scenario sensitivity: recode each independent in turn as not Democratic-caucusing, starting with NE-SEN, and exclude that race from both the expected and the actual Democratic-caucus seat totals.
11. **Primary analysis.** One primary contrast: Kalshi (raw A probability, rule 5) versus the fixed equal-weight mean of the Economist and VoteHub A probabilities, on Brier over the 15 races Cook rated anything but Solid. This is a market-versus-mixed-benchmark comparison, because VoteHub Complete incorporates Kalshi prices. Report paired leave-one-race-out effects as influence diagnostics, and bootstrap intervals separately as conditional sensitivities (Part 2). Everything else is secondary and reported descriptively: other metrics, the all-35 and 11-race samples, the other Cook mappings, the separated source comparisons in Part 2 item 5, and volume weights. No multiplicity adjustment is applied, and secondary results are not described as confirmatory.
12. **Sample definitions.** Primary contrast: the 15 non-Solid races. Secondary: all 35 races. Robustness: races where the average of Kalshi, Economist and VoteHub A probabilities is between 10% and 90% (11 races), which is defined using sources under test.
13. **Calls correct.** A source's favorite is the side it gives above 0.50. A probability of exactly 0.50 (Kalshi on IA-SEN) makes no call, and Cook's 7 Toss-Ups make no call. Always report correct calls alongside the number of calls made. Calls-correct is descriptive context. All four sources favor the same candidate in all 28 races where Cook makes a directional call, so their accuracy on that set ties by construction. Differences arise only within the seven Toss-Ups.
14. **Cook House seat count.** The primary directional expected-seat calculation applies House hit rates to Cook's seat counts: Solid D 186 at 0.9997, Likely D 18 at 0.961, Lean D 18 at 0.907, Toss-Up 18 at 0.478, Lean R 17 at 0.049, Likely R 14 at 0.023, Solid R 164 at 0.0003. This gives 229.3764. Alternatives: the symmetric all-race mapping of rule 1 (Solid 0.99, Likely 0.97, Lean 0.94, Toss-Up 0.50, applied in both directions) gives 230.60. Changing only the Toss-Up rate to 0.50 gives 229.7724. A separate deterministic allocation treats the 222 Democratic-favored seats as certain Democratic wins, the 195 Republican-favored seats as certain Republican wins, and splits the 18 Toss-Ups evenly, giving 231.
15. **Cook House control.** Cook's firm Democratic seats (Solid, Likely, Lean) total 222, above 218, so Cook's call is Democratic control. It is scored as hit or miss only and kept out of the Brier and log-loss tables for House control.
16. **House vote.** The national House vote used for generic-ballot scoring is the two-party Democratic share of total votes cast from one stated source. A second version excludes uncontested seats where the data allow.
17. **Baselines.** Brier skill scores use two references: Cook under the primary mapping, and a constant-confidence baseline that gives 0.95 to the Cook-favored side in every non-Toss-Up race and 0.50 in Toss-Ups. A uniform 0.50 baseline is also reported.
18. **Test list.** The tests below are fixed in advance. Anything added later is labeled exploratory.

## Data Notes

- The RCP and Silver "Average" fields hold A minus B margins. Scoring uses the A and B shares.
- House seat counts may take days to finalize; score House control first and seats later.
- Snapshot timestamps span about four hours on Nov 2.

## Part 1: General Audience

1. **Calls correct.** Correct calls and calls made for each source, for all races where the source made a call, for the Cook non-Solid set, and for the common set of 28 (rule 13).
2. **Expected vs. actual seats.** Sum each source's A win probabilities across the 35 races and compare with actual A wins. Report the standard deviation implied by each source's probabilities, noting that independence omits cross-race covariance and can understate spread when outcomes are positively correlated. Seat error and control follow rule 10.
3. **Biggest misses.** Winners each source gave the lowest probability, side by side for markets and forecasters.
4. **Market vs. model disagreements.** Races where Kalshi differed most from the Economist and VoteHub average, and which side was closer. Report the same comparison against the Economist alone, since VoteHub Complete incorporates Kalshi. Kalshi sits above the model average in 6 of the 7 Toss-Ups, so report whether these disagreements share a direction.
5. **House.** Probability each source gave the winning party (Kalshi, Economist, VoteHub) and Cook's hit or miss. Then seat-count error for Cook (rule 14), the Economist and VoteHub once seats are final.
6. **Cook by bucket.** Outcomes by rating (Likely, Lean, Toss-Up). Descriptive only; each direction bucket holds 2 to 7 races.

## Part 2: Statistics (Portfolio)

1. **Proper scoring.** Brier score and log loss per source under rule 4, on all races and each subset. Brier skill score against both references in rule 17.
2. **Paired comparisons.** Per-race loss differences between sources. The primary contrast follows rule 11. Report a paired leave-one-race-out analysis, which drops each race in turn from both sources, as an influence diagnostic rather than an interval. A sign-flip permutation test on the nonzero differences is reported as an assumption-qualified analysis: it assumes the differences are symmetric about zero under the null and independent across races, which is an additional assumption beyond equal expected accuracy. Bootstrap intervals are percentile intervals from resampling races with replacement, at the 95% level, with 10,000 replicates and seed 20261104, and are conditional sensitivities. They describe this election's races and do not capture uncertainty across national election environments. Report the number of nonzero pairs and intervals, not winners.
3. **Calibration diagnostics.** Simulate outcomes from each source's probabilities and locate the observed Brier within the simulated distribution, using 20,000 draws and seed 20261105. Dependence uses a Gaussian copula so each race keeps its marginal win probability exactly: latent z_i = sqrt(rho) * S + sqrt(1 - rho) * e_i, with S and e_i standard normal, and y_i = 1 when z_i is at or below the standard normal quantile of p_i. The dependence parameter rho is the correlation of the latent normal variables, not the correlation between binary race outcomes. It is a sensitivity grid (0, 0.1, 0.25, 0.5) with no estimated value, and rho = 0 is the independent case. Add Spiegelhalter's Z with its independence assumption stated. These are limited diagnostics at small n.
4. **Vote share accuracy.** Error in two-candidate share for the Economist, VoteHub, RCP and Silver. Report whether Silver's weighted average differs from RCP's on the common races. Report mean signed error (bias), then split each source's error into the mean error across the evaluated races and each race's deviation from that mean, since errors across races are correlated. Poll comparisons use the common set of races.
5. **Does the market add information? (descriptive).** Compare Kalshi against the Economist and VoteHub mean using Brier (the primary contrast of rule 11), and report two separate secondary comparisons. Kalshi versus the Economist asks how Kalshi compared with a polls-and-fundamentals forecast whose published description lists no market input. Kalshi versus VoteHub Complete asks whether the market-informed system scored better than Kalshi alone, and it does not establish which component caused any difference. Also compare against one blend with weights fixed before outcomes are examined: 0.5 Kalshi and 0.5 model mean. That blend adds Kalshi exposure to a benchmark that already contains it through VoteHub, so it tests another forecast combination and does not add a new information source. Other blend weights are exploratory. A better realized score than the fixed model mean in this one election is a descriptive finding and supports no general conclusion that markets add information.
6. **Favorite-longshot pattern (exploratory).** Check whether Kalshi overprices low-probability outcomes (for example 4.5% on AR-SEN where models sit at 1%). Volume-based tests are in Part 3.
7. **Cook sensitivity.** Rerun the above under all three Cook mappings.
8. **Power note.** The simulation draws outcomes from the Economist and VoteHub mean, so its results are conditional on that model. Under independence, the standard deviation of the mean Brier gap between Kalshi and that mean is about 0.01 on all 35 races and about 0.02 on the 15 competitive races. Report how the specified dependence scenarios change both. Rough normal approximations suggest detectable gaps at 80% power of about 0.03 and 0.06 respectively, assuming a two-sided 5% significance level. The expected gap in that simulation is 0.004 to 0.008, so small differences cannot be detected at this sample size.

## Part 3: Volume

Kalshi_Total_Volume is the recorded cumulative trading volume in each race's market as of the snapshot; units await verification against the original source field. Shares are computed against the recorded sum across the 35 races, about $212.2 million. Volume is highly concentrated: TX-SEN alone holds 36.0%, the top three races (TX, MI, ME) hold 57.9%, and the 15 non-Solid races hold 96.5%. Eleven races have recorded volume under $250,000, all rated Solid. Volume is the market-specific dimension of the series. It measures cumulative trading activity and is not a measure of capital invested or of liquidity.

### General Audience

1. **Where trading volume was.** Share of total volume in races where the market favorite won, in races where it lost, and in races with no market favorite (IA-SEN at 0.50).
2. **Volume by Cook rating.** How much trading volume sat in Toss-Up, Lean, Likely and Solid races.
3. **Concentration.** How much of the market's volume was one race (TX-SEN) and what that implies about what traders cared about.

### Statistics

1. **Low-volume filter.** Rerun market scores excluding the 11 thin markets and flag any result that depends on them.
2. **Volume-weighted scoring (secondary).** Weight each race's loss by w_i = V_i / sum of V, using Kalshi volume V_i. Apply the same weights to every source so the comparison stays fair.
3. **Volume vs. accuracy (exploratory).** Spearman correlation between log volume and Kalshi's surprise (realized loss minus expected loss, p(1-p)). Raw volume against loss is confounded, because close races draw both volume and higher expected loss.
4. **Volume vs. market-model gap (exploratory).** Whether the absolute gap between Kalshi and the Economist alone, and between Kalshi and the Economist/VoteHub average, narrows as volume rises. The average contains Kalshi information, and VoteHub's reliance on last-trade prices rises with liquidity, so the Economist-only gap is the cleaner version.

Caveat: volume is cumulative at the snapshot. It does not measure liquidity at the time. Open interest and bid-ask spread were not captured.

## Limitations

- Small effective sample. Competitive races share one national environment, so they behave like fewer independent tests than their count suggests.
- The market-versus-model comparison rests heavily on a few correlated Toss-Ups (TX, KS, IA, AK, OH), where Kalshi sits 10 to 17 points above the model average. Those races resolve together if the national environment moves, so they carry less independent information than their count.
- Kalshi is a single market, so conclusions about markets in general are limited to Kalshi.
- Cook's mapped probabilities come from its published historical hit rates, which are self-reported and pooled across House, Senate, governor and presidential races. The all-race Lean and Likely rates (93.7%, 97.1%) are mostly House rates. The Senate-only rates are higher for Lean (98.1%, n = 103) and similar for Likely (97.8%, n = 93). The plan reports all three mappings and cannot determine from this sample which is better calibrated for 2026. In the House, Cook's Democratic-favored Lean and Likely calls have missed more often than its Republican-favored ones (Lean: 90.7% against 95.1%). The Senate buckets are small and misses cluster in wave years, so the effective sample is smaller than the counts suggest. The 0.99 Solid cap and the 0.50 Toss-Up value are assumptions. The hit rates also predate mid-decade redistricting changes.
- Snapshot timing differs across sources and across rows, and prices moved between Nov 2 and election day. Unequal timing can favor or disadvantage any source.
- Markets are not independent of forecasters; models and polls feed into market prices. VoteHub Complete takes Kalshi prices and expert ratings, including Cook, as direct inputs, so Kalshi versus VoteHub and Cook versus VoteHub are not independent comparisons, and agreement among them is not independent confirmation. VoteHub's market influence is largest in close races, which are the races in the primary sample. VoteHub's Kalshi input comes from its own capture time, which can differ from the recorded Kalshi snapshot. The Economist and VoteHub also draw on overlapping polls, so averaging them adds limited independent information.
- No VoteHub Legacy forecasts were collected, so no market-free VoteHub benchmark is available and the Complete forecasts cannot be separated into their inputs.
- Raw Kalshi prices can include a small overround where A and B sum above 1 (AK-SEN, ID-SEN). Normalizing removes it but conditions on A or B winning. The normalized sensitivity shows whether the choice matters.
- Coding independents as Democratic-caucusing is an assumption. Control results are shown under the recoding sensitivity in rule 10.
- Significance tests and bootstrap intervals describe this election's races and depend on the stated assumptions. They do not establish how forecasters or markets perform across election environments.

## Sources

- [VoteHub 2026 midterm methodology](https://votehub.com/wp-content/uploads/2026/05/2026_votehub_midterm_methodology.pdf)
- [How accurate are Cook Political Report's race ratings](https://www.cookpolitical.com/analysis/national/cpr-archives/how-accurate-are-cook-political-reports-race-ratings)
- [The Economist, 2026 US midterms prediction model](https://www.economist.com/interactive/2026/us-midterms/prediction-model/house)
