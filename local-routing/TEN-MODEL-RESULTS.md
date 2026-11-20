# Ten quarterly model attempts: MISO and NYISO

Status: research only; do not use for production forecasts. Generated 2026-11-20 from the existing model-ready panels. Last source quarter: 2025Q4. The IA outcome is distinct for MISO; NYISO combines IA and operation.

## Experiment

Ten models were attempted for each region: an age-only logistic comparison; three regularized logistic models using age, log MW and technology; four histogram gradient-boosted models with different tree and regularization settings; and two random forests with different minimum leaf sizes. A separate empirical age-bucket competing-risk model approximates the dashboard benchmark, retrained at each historical origin. Its outputs and the candidates are tested on the same records and horizons.

Each model is trained on quarterly observations strictly before the forecast origin. The model predicts each subsequent quarter while age advances and the chosen technology and capacity stay fixed. Quarterly stay, withdrawal and event probabilities are combined as competing risks. Historical January 2016, 2018, 2020, 2022 and 2023 origins are tested, with 1-, 2-, 3- and 5-year horizons where follow-up can be assessed. Older 2018 and 2020 results selected the best feature-based candidate by equal-weight mean multiclass Brier, with log loss used to break ties. 2022 and 2023 are later checks. These years have been inspected in prior research and are not a fresh untouched final test. Records without full individual follow-up are excluded; this can bias complete-case results. Horizons that rely on the final incomplete 2025Q4 are excluded. The same project can appear at multiple origins; results are not independent observations.

Results, including Brier, log loss, AUC, predicted and observed event and withdrawal rates, and subgroups, are in `ten-model-evaluation.json`. `empirical-benchmark-evaluation.json` contains the comparator. Results without enough events have no AUC. Outcomes vary together: unresolved is the remaining probability after IA/operation and withdrawal.

## Closest candidates

The best feature-based MISO candidate on the selection periods was `tree_deep` (histogram gradient boosting, 15 leaves, minimum 100 observations per leaf). Its equal-weight mean multiclass Brier across 2018/2020 available horizons was 0.650 versus 0.536 for the empirical age benchmark; lower is better. On 2022/2023 available horizons the candidate averaged 0.463 versus the benchmark's 0.488. That does not establish general superiority. On 2020 MISO wind projects at three years, the candidate estimated 26.9% withdrawal versus 57.0% observed (100 projects).

The best feature-based NYISO candidate on the selection periods was `tree_shallow` (histogram gradient boosting, five leaves, minimum 150 observations per leaf). Its 2018/2020 mean multiclass Brier was 0.554 versus the empirical benchmark's 0.632. On 2022/2023 available horizons, the candidate and benchmark were essentially tied: 0.546 and 0.546. At the 2023 origin over two years, the candidate estimated 23.0% withdrawal versus 81.1% observed (492 projects). Both models badly missed the withdrawal wave.

The artifacts `miso-quarterly-research.joblib` and `nyiso-quarterly-research.joblib` refit the respective feature-based candidates on available historical rows and are marked `release_ready: false`. Run `research_scenario.py --region MISO --technology Solar --mw 100` to get quarterly research outputs. It is not connected to the website. `test_research_scenario.py` checks probability consistency and one-at-a-time sensitivity of solar 50 vs 200 MW and solar vs wind at 100 MW for both regions. The check proves input wiring, not the truth or reliability of an effect. Values can vary non-monotonically with project size.

## Limitations and release gate

All panel rows for a project carry the same capacity and technology. These values may be later snapshots, so their apparent association in a historical test may contain information unavailable at the forecast time. MISO preparation excludes some projects using eventual outcome information, introducing selection risk. NYISO withdrawal dates include proxies, and its event mixes IA and operation. No separate storage MW/duration or service type is used by these candidates. Quarterly tests describe projects observed at the chosen origin; they do not prove calibration for a newly proposed project. Forecasts do not predict changes in future queue conditions. Class probability metrics are not comparable to a binary Brier unless labeled as such. The latest dates leave no fully observed five-year 2022/2023 test.

Do not deploy these candidates until point-in-time source versions, appropriate censoring, current model environment and actual website inference have been verified. A selection-period leader is not evidence that its outputs are suitable for decisions. The website's age-based models remain in place.
