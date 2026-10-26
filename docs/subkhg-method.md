# Sub-KHG prioritisation: the method adopted

Methodological report, repeat-prioritisation (`subkhg`), 2026-10-26. Diagram: [figures/subkhg_method.drawio](figures/subkhg_method.drawio) (open in draw.io; rebuilt by `docs/figures/make_subkhg_method.py`). Validation: [re-peat/reports/subkhg_validation.md](../../re-peat/reports/subkhg_validation.md). Weights are provisional and not agreed with the team.

## 1. What it delivers

For each sub-KHG of one KHG: a need score for rewetting intervention (sekat kanal, sumur bor, pompa), its rank (`peringkat`, 1 = most need) and a class (`kelas`: tinggi, sedang, rendah, the tertiles within the KHG). The team's earlier rank-sum is computed beside it. The table `subkhg_priority.csv` hands the order and the KHG water deficit to repeat-pump.

The ranking answers which sub-KHG need intervention most. Which measure fits where (canal blocks, wells, pumps) is read afterwards from the feasibility columns and from repeat-pump.

## 2. Where it sits in the chain

| Step | Module | Gives the ranking |
|---|---|---|
| 1. KHG inputs | repeat-prioritisation `subkhg.prepare_inputs` | canals, rivers and existing canal blocks clipped from `_data` into `_khg/<khg>/00_inputs/` |
| 2. DTM | repeat-dem | the DTM for slope and lift |
| 3. Sub-KHG units | repeat-delineation | `02_delineation/subkhg_units.gpkg` |
| 4. Neraca air | repeat-neraca | P − ET per unit with its stability flag; the KHG deficit |
| 5. Ranking | repeat-prioritisation `subkhg.run` | this report |
| 6. Pumping and blocks | repeat-pump | reads `subkhg_priority.csv` |

The ranking does not repeat what the earlier steps produce: the water balance and the deficit come from neraca air; rain-based indicators (dry days, TerraClimate deficit) are not computed, because rain products cannot separate sub-KHG (neraca air method report, decision 1).

## 3. Inputs

| Input | Source | Grid or form | Years | Gives |
|---|---|---|---|---|
| Sub-KHG units | `02_delineation/subkhg_units.gpkg` (repeat-delineation) | polygons | | the units |
| Burnt area | `_data/burnt_area_2015_2026_Indonesia.gpkg` (per-year flags `BA_yyyy`) | polygons | 2015-2026 | burnt share, repeat burns, this year's burns, validation target |
| Hotspots | `_data/hotspot_viirs_snpp_2012_2025.gpkg` (NASA FIRMS VIIRS S-NPP; type 0, confidence n and h) | points | 2012-2025 | hotspot density, validation target |
| This year's hotspots | `_data/_data_hotspot_Januari_September_2026.gpkg` (KLH, MODIS; medium and high confidence) | points | 2026 to 15 September | hotspot density this year, high-confidence share |
| Canals by class | `_data/kanal_osgm_khg_existing_Indonesia.gpkg` (`KODE_KANAL` 1 primary, 2 secondary, 3 tertiary) | lines | 2025 | canal km per km² by class |
| Peat extent | `_data/peat_extent_gfw_v20230315_z11.tif` (GFW composite, CC BY 4.0) | 76 m | | denominator of the fire rates |
| KHG canals, rivers, canal blocks | `00_inputs/canals.gpkg`, `rivers.gpkg`, `blocks.gpkg` (existing blocks, REALISASI) | lines, points | | reach, distance to water, blocks needed and existing |
| Protected function | `_data/landstatus/FEG__Indonesia__2017__Rev_Tipologi.gpkg` (`FEG_KGHLTR` = Indikatif Fungsi Lindung E.G.) | polygons | 2017 | protected share |
| DTM, peat depth | `Peat depth and DTM/` (site config) | rasters | | slope of canals, lift above water, peat depth |
| Sentinel-2 L2A | Planetary Computer `sentinel-2-l2a` (B8A, B11, B04, SCL cloud mask) | 20 m bands read onto the 30 m grid | dry season (Aug-Oct) of each baseline year | NDMI, NDVI |
| Land cover | ESA WorldCover (Planetary Computer) | 10 m | 2020/2021 | forest share |
| Surface water | JRC Global Surface Water seasonality (Planetary Computer) | 30 m | | permanent water (10 or more months) for distance to water |
| Water table | SiTMAT concession stations (`repeat-sitmat`) | points, daily | 2026 | days deeper than 0.4 m, recession rate |
| Neraca air | `03_neraca/runs/balance/neraca_balance_unit.csv`, `runs/deficit/neraca_khg.csv` | table | 2018-2025; 2026 | P − ET; KHG deficit |

All except Sentinel-2, WorldCover and JRC water are local files in `_data` (catalogued in `re-peat/sites/data_catalog.csv`). The cloud layers are fetched once per KHG into `_khg/<khg>/cache/` (`subkhg.run --fetch-only`).

## 4. Processing

**Step 1. Fire and canals per unit** (`subkhg.national_layers`). The units are handed to `national.profile.build_profile` in place of the national KHG, so the sub-KHG and national levels count fire and canals with the same code. Rates are per km² of peat (GFW extent), as AGENTS.md requires.

- `u_fire_freq`: mean annual burned share of the unit's peat over the baseline years; `u_burn_repeat`: share burned two or more times in the baseline; `u_burned_now`: this year's burned share (reported).
- `u_hotspot`: VIIRS hotspots per km² of peat per year; `u_hotspot_now`: KLH hotspots of this year per km² of peat, with `hs_now_high_share`.
- `u_canal_primary`, `_secondary`, `_tertiary`: canal km per km² by class.
- Held-out targets for the validation years: `v_burned_frac`, `v_hotspot`.

**Step 2. Indicators on a 30 m grid** (`common.indicators`), means over the unit:

- `u_ndmi`, `u_ndvi`: per year the median of the cloud-masked Aug-Oct Sentinel-2 composite, then the mean over the baseline years with data.
- `f_reach`: share of the unit within 200 m of a canal (60 m on land that has burned): where canal blocks can raise the water table.
- `u_ipg_gap`: missing canal blocks (metrik IPG). Blocks needed on the primary and secondary canals = canal length ÷ spacing, spacing = 0.4 m ÷ median canal slope (from the DTM), kept between 50 and 2,000 m (category A). `u_ipg_gap` = 1 − existing ÷ needed, at least 0.
- `f_water_dist`: mean distance to permanent water (JRC, 10 months or more) or a river; `f_lift`: median height of the land above that water (DTM).
- `i_peat_depth`, `i_forest` (WorldCover tree cover and mangroves), `i_protected` (FEG protected function).
- `u_tma`, `u_tma_recession`: share of days with the water table deeper than 0.4 m, and the mean rate at which it deepens (mm/day, between readings at most 10 days apart), averaged over the SiTMAT stations in the unit (2026 only).

**Step 3. Neraca air** (`extra_indicators`). `neraca_balance_unit.csv` is merged; `p_minus_et_mean_mm` fills the rank-sum's water-balance slot where `balance_stable_ok` is 1, and the balance columns are left empty where it is 0 (`common.pipeline.gate_balance`).

**Step 4. Score** (`subkhg.prioritise`).

1. Each indicator is scaled to 0-1 between its 5th and 95th percentile within the KHG, turned so that 1 is the most need. It is scored only if at least min(20, max(3, n/2)) units have a value; otherwise it is reported only.
2. Urgency U and stakes S are weighted means of the scaled indicators of their group that the unit has (section 5).
3. **Need = 0.8 U + 0.2 S.** Feasibility (lift) is reported, not ranked.
4. Classes are the tertiles of the need score within the KHG.
5. The rank-sum (section 7) is computed alongside; `scoring.method` chooses which one sets `kelas` and `peringkat`, and `laporan.json` gives their agreement.

**Step 5. Checks.** Indicator pairs with Spearman above 0.8 are flagged. Weight sensitivity: 300 draws of weights from a Dirichlet distribution centred on the weights (concentration 20); `p_prioritas1` is the share of draws in which a unit is in the top class. Held-out validation is section 8.

## 5. Parameters and weights

| Group | Indicator | Weight | More need when |
|---|---|---|---|
| Urgency | burnt share `u_fire_freq` | 2 | higher |
| | repeat burns `u_burn_repeat` | 1 | higher |
| | hotspots `u_hotspot` | 1 | higher |
| | hotspots this year `u_hotspot_now` | 1 | higher |
| | NDMI `u_ndmi` | 1 | lower (drier) |
| | canals primary, secondary, tertiary | 0.5, 0.3, 0.2 | denser |
| | missing blocks `u_ipg_gap` | 1.5 | more missing |
| | reach `f_reach` | 1.5 | more land near canals |
| | distance to water `f_water_dist` | 1 | farther (wells needed) |
| | forest share `i_forest` | 1 | less forest |
| | SiTMAT `u_tma`, `u_tma_recession` | 1, 1 | deeper, faster (only with enough stations) |
| Stakes | peat depth `i_peat_depth` | 2 | thicker |
| | protected function `i_protected` | 1 | larger share |
| Reported only | NDVI, neraca balance, single canal density (replaced by classes), lift, this year's burns, rates per area | 0 | |

Other parameters: 30 m grid; NDMI months August-October; reach 200 m (60 m on burnt land); permanent water 10 months; block spacing 0.4 m ÷ slope, 50-2,000 m; need = 0.8 U + 0.2 S; scaling between the 5th and 95th percentile within the KHG; baseline 2015-2022 (Permen LHK 7/2022 counts land burnt since 2015). Weights are the defaults of the code and the national profile, not agreed with the team.

## 6. Outputs

In `_khg/<khg>/04_prioritisation/` (the current runs: `national_layers/`):

| File | Content |
|---|---|
| `unit_prioritas.gpkg`, `.csv` | per unit: every indicator, scaled values (`n_*`), `skor_urgensi`, `skor_dampak`, `skor_need`, `kelas`, `peringkat`, rank-sum score and rank, `p_prioritas1`, coverage `cakupan_*` |
| `laporan.json` | weights, indicators used, coverage, correlated pairs, sensitivity, validation |
| `subkhg_priority.csv` | `unit_id, priority_rank, deficit_mm` (the KHG deficit of neraca air), `design_period_days` for repeat-pump (contract C6) |
| `validation/<fold>/` | the reruns of the held-out validation |
| `peta_prioritas_<khg>.png` | map of the classes |

Reports: `repeat-subkhg-report` (numbers of a run), `repeat-subkhg-dashboard` (map page), `scripts/validate_subkhg.py` (validation).

## 7. What changed from the team's earlier method

The earlier method (slide "Contoh Parameter Penentuan Prioritas Pembasahan dalam 1 KHG", Kahayan-Sebangau; [prior_method.md](prior_method.md)) ranks the sub-KHG by 8 indicators, sums the ranks with equal weights, and is kept as the rank-sum.

| Earlier | Now |
|---|---|
| ranks summed, equal weights | need score on scaled values with explicit weights; the rank-sum kept beside it |
| NDMI and NDVI | NDMI scored (Sentinel-2 at 20 m, cloud-masked season median); NDVI reported |
| peat depth | in the stakes |
| water decline, water balance, deficit months, dry days | from repeat-neraca, used only where the order of units is trustworthy; dry days dropped (rain products cannot separate sub-KHG) |
| hotspot count | burnt share, repeat burns, hotspot density and this year's hotspots, from the national layers, per km² of peat |
| not in the slide | drainage: canals by class, canal reach and missing blocks; distance to water; protected function; SiTMAT where stations are dense enough |
| not tested | held-out validation on two El Nino years (section 8) |

## 8. Validation and results

Runs of 2026-10-26 (`_khg/<khg>/04_prioritisation/national_layers/`), baseline 2015-2022, NDMI at 20 m.

| | Sugihan-Lumpur | Kampar-Gaung |
|---|---|---|
| sub-KHG | 30 | 26 |
| classes tinggi / sedang / rendah | 10 / 10 / 10 | 9 / 8 / 9 |
| need score against rank-sum: Spearman, top-class overlap | 0.58, 83 % | 0.76, 60 % |
| weight sensitivity: units keeping their class in 300 draws; median rank spread | 73 %; 4.5 ranks | 77 %; 2.9 ranks |
| strongly correlated pairs (Spearman above 0.8) | tertiary canals with reach 0.87; peat depth with lift −0.89 | tertiary canals with reach 0.93; peat depth with lift −0.87 |
| SiTMAT scored | no (too few units with stations) | yes |
| KHG deficit passed to repeat-pump | 290 mm | 7 mm |

NDMI at 20 m orders the units as the earlier 60 m test did (Spearman 0.997-1.000 per year, 2019-2021). Valid NDMI pixels cover 94-100 % of the units from 2016 at Sugihan-Lumpur and from 2018 at Kampar-Gaung (2022 lower: 58 % and 87 %); 2015 has no Sentinel-2 L2A scenes at Sugihan-Lumpur.

**Held-out validation** ([re-peat/reports/subkhg_validation.md](../../re-peat/reports/subkhg_validation.md)). Indicators of the earlier years, burned share of each unit's peat in the test year; Spearman with a 90 % bootstrap interval; units that burned in the test year in brackets:

| Score | Kampar-Gaung 2019 (11) | Kampar-Gaung 2023 (6) | Sugihan-Lumpur 2019 (13) | Sugihan-Lumpur 2023 (9) |
|---|---|---|---|---|
| need score | 0.61 (0.34 to 0.80) | 0.29 (−0.01 to 0.54) | 0.37 (0.06 to 0.62) | 0.17 (−0.17 to 0.46) |
| urgency part only | 0.57 (0.27 to 0.79) | 0.30 (0.01 to 0.56) | 0.54 (0.24 to 0.75) | 0.30 (−0.01 to 0.56) |
| fire history alone | 0.38 (0.02 to 0.68) | 0.22 (−0.06 to 0.48) | 0.64 (0.39 to 0.82) | 0.36 (0.09 to 0.61) |
| rank-sum | 0.66 (0.42 to 0.81) | 0.47 (0.22 to 0.69) | 0.25 (−0.04 to 0.52) | 0.10 (−0.21 to 0.39) |

Reading:

- All scores point at later fire better than chance in most folds, but with 26-30 units the intervals overlap: no score is clearly better than another.
- The urgency part predicts later fire at least as well as the need score in most folds. The stakes part (peat depth, protected function) says what is at risk, not where fire comes, so it lowers the fire prediction by design.
- At Sugihan-Lumpur fire history alone predicts later fire best; at Kampar-Gaung the full urgency part does better than fire history. The other indicators (drainage, NDMI, distance to water) add to fire prediction in one KHG and not in the other.
- The rank-sum is the best score at Kampar-Gaung and the weakest at Sugihan-Lumpur.
- Fire is the only outcome available for testing. Canals, missing blocks and reach describe the need for rewetting itself, which no held-out data can test yet. The weights therefore cannot be set from the validation alone; they need the team's judgement (AHP), with the validation as a check.

## 9. Limits

- 26-30 units per KHG: validation intervals are wide, and a few large fires decide them.
- Only Sugihan-Lumpur among the selected KHG has sub-KHG units so far (Kampar-Gaung is a test site); the other KHG wait for repeat-delineation.
- SiTMAT covers one season and few units; it enters the score only where enough units have stations.
- Canals are an OSM-derived layer without flow direction; existing blocks come from the BRGM structures (REALISASI) and may be incomplete per KHG.
- The weights are provisional; the team has not agreed them (an AHP session is the proposed route).

## 10. How to run

Environment: `REPEAT_KHG`, `REPEAT_DATA`, `REPEAT_HUB`, `REPEAT_WORK`, `SITMAT_PROCESSED`. From `repeat-prioritisation`:

```bash
repeat-subkhg --config ../re-peat/sites/<khg>/subkhg.yaml --fetch-only     # Sentinel-2, WorldCover, JRC, once per KHG
repeat-subkhg --config ../re-peat/sites/<khg>/subkhg.yaml --skip-fetch     # score
python scripts/validate_subkhg.py --config ../re-peat/sites/<khg>/subkhg.yaml --out ../re-peat/reports/subkhg_validation.md
python docs/figures/make_subkhg_method.py
```

The site config (`re-peat/sites/<khg>/subkhg.yaml`) names the units, the KHG vectors and rasters, `national_layers: {config: ...}`, `extra_indicators` (the neraca balance), `priority_export` (the neraca deficit) and the years.
