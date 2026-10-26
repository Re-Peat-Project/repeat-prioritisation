# Sub-KHG prioritisation

Ranks the sub-KHG inside each KHG by **need for intervention** (sekat kanal, sumur bor, pompa). The national run asks which KHG deserves attention. This one asks which sub-KHG needs the most, so that the right measure can be chosen for it afterwards.

```
subkhg/
  run.py           entry point and preset (30 m grid, 2015 baseline, need ranking)
  prepare_inputs.py clips the big national vector files (canals, rivers, blocks) to one KHG
  check_inputs.py  looks at the inputs of a run (canal classes, raster floors, stations) and writes markdown
  report.py        writes the markdown report of a real-data run from its output folders
  prioritise.py    need ranking: score_need(df, cfg) -> (ranked table, report)
```

`common/` holds what both programs share: grid, source fetchers, indicators, normalisation, group scores, sensitivity and validation. `run.py` plugs `delineate` and `score_need` into `common.pipeline.main` as hooks. Nothing in this folder changes the national run.

## Run

```bash
python -m subkhg.run --print-default-config > configs/local/subkhg.yaml     # edit paths
python -m subkhg.run --config configs/local/subkhg.yaml                     # fetch, delineate, score
python -m subkhg.run --config configs/local/subkhg.yaml --fetch-only        # just build the cache
python -m subkhg.run --config configs/local/subkhg.yaml --skip-fetch        # re-score (e.g. new weights)
```

For a real KHG, first cut the national vector files down to that KHG (runs otherwise re-read hundreds of MB each time), keeping only the features you need:

```bash
python -m subkhg.prepare_inputs --khg-shp <KHG shapefile> --khg-id 71 --out $REPEAT_KHG/14.02-04-05.01_kampar_gaung/00_inputs \
    --canals kanal.gpkg --rivers sungai.gpkg --blocks infrastruktur.gpkg \
    --blocks-where "Jenis == 'Sekat Kanal' and KETERANGAN == 'REALISASI'"
```

Canal classes matter: if every canal is an outlet, a dense plantation network breaks the KHG into tiny pieces. Set `units.subkhg.canal_class_field` and `outlet_canal_classes` (compared in lower case, so `["Kanal Primer"]` for the BRGM canal file), and `params.ipg_canal_class_field` and `ipg_canal_classes` for the canal-block counts.

Check the inputs before running (`python -m subkhg.check_inputs --config ... --out ../re-peat/sites/<khg>/reports/<run>_inputs.md`): it lists the canal classes, whether the peat depth raster has a floor value, and how many water-table stations lie inside the KHG. After a run, `python -m subkhg.report --subkhg-config ... --neraca-config ... --out docs/reports/<run>.md` writes the numbers of the run. A worked example is `docs/runbook_kampar_gaung.md`.

Delineation is its own repository, `repeat-delineation` (`python -m repeat_delineation --config ...`). It writes `subkhg_units.gpkg`; score those polygons with `units: {mode: vector, path: <its out>/subkhg_units.gpkg}` in the config of `subkhg.run`. Edit the polygons first if needed; `khg_id` and `unit_id` are kept. The old `units.mode: subkhg` (delineating inside this program) was removed.

Run from the repo root. Needs the sub-KHG polygons; `rasters.dtm` (the pump-lift and reach indicators), canals, rivers, peat depth, settlements and the rest are optional. A missing layer lowers coverage (`cakupan_*`) and never stops a unit from being ranked.

## Steps

1. **Delineate** in `repeat-delineation`; the polygons are the input here.
2. **Indicators** for each sub-KHG (`common/indicators.py`), from the baseline years only.
3. **Normalise** each indicator to 0–1 (5th–95th percentile) within the KHG.
4. **Score** ([prioritise.py](prioritise.py)): need, stakes and feasibility group scores, then the need ranking and classes.
5. **Checks:** indicator correlation, weight sensitivity, validation on held-out years.

## 1. Delineation

Moved to the `repeat-delineation` repository (README there: inputs, method, parameters, `--sweep`, outputs). `units.mode: vector` takes its `subkhg_units.gpkg`, or your own polygons (e.g. the 16 Kahayan–Sebangau sub-KHG); `hex` uses 1 km² hexagons. The same scoring applies to all three. `delineation_report.json`, written next to the polygons, is read by `subkhg.dashboard`.

## 2–4. Need ranking

Need is in group `u`, stakes in `i`, feasibility in `f`.

| Group | Indicators | Why |
|---|---|---|
| **Need** | `u_fire_freq`, `u_hotspot` | Recurrent fire means persistently low water |
| | `u_ndmi` | Dry surface in the dry season |
| | `u_canal_density`, `f_reach`, `u_ipg_gap` | Drained peat and missing canal blocks: sekat kanal |
| | `f_water_dist` | Far from dry-season water: sumur bor |
| | `i_forest` (inverted) | Intact forest needs less; degraded land more |
| *(off)* | `u_wb_mean`, `u_deficit*`, `u_dryspell`, `u_spell14` | Climate, 4–25 km. Weight 0 by default: constant inside a KHG. Within a KHG they vary only through interpolation between cells or, for the water balance, through forest interception, which made forested units look drier and cancelled `i_forest`. Set a weight in `indicators:` to use them (e.g. with `normalise_scope: all`), and set `sources.era5.enabled: true`: the sub-KHG run does not fetch ERA5 rainfall by default, because it takes about 4 minutes per KHG-year (more for the TerraClimate fallback). The neraca air module is meant to replace them. |
| | `u_tma`, `u_tma_recession` | Logger water table (SiTMAT or CSV, see the main README). Most sub-KHG have no station, so it is often reported but not scored. `n_tma_stations` shows the coverage. |
| **Stakes** (weight 1 − α) | `i_peat_depth`, `i_protected`, `i_exposure` | Carbon at risk, protected function, nearby settlements |
| **Feasibility** (reported only) | `f_lift`, `f_access` | Pump lift and road access, for choosing the measure |

- `skor_urgensi` = need, `skor_dampak` = stakes, `skor_kelayakan` = feasibility.
- `skor_risiko` = α · need + (1 − α) · stakes, with α = 0.8 (`scoring.alpha_urgency`). It's the ranking score; the name is kept for the shared validation code.
- The tidal adjustment (`tidal_mode: downweight`) reduces need by 70% × tidal share.
- Classes are tertiles of `skor_risiko`: **Kebutuhan intervensi: tinggi / sedang / rendah**. Within each KHG by default (`normalise_scope: khg`), or across all KHG with `all`.
- Override classes: **Pengaruh pasang surut: pantau** (`tidal_mode: exclude`, ≥ 50% tidal) and **Dikecualikan (pengelolaan lahan)** (≥ 50% in an excluded concession type, default IUP).
- `peringkat` = 1 for the highest need. Feasibility never changes the rank.

Weights, AHP matrices and `enabled: false` work as in the main README. Defaults for the three indicators moved to need are in `NEED_INDICATORS` ([prioritise.py](prioritise.py)). Anything in your config's `indicators:` block overrides them.

**Not yet included: neraca air at sub-KHG scale.** `u_wb_mean` is TerraClimate at about 4 km. A finer water balance is planned as its own module (the `repeat-neraca` repository) that plugs in through the extra-indicator tables below.

## Rank-sum method (the team's earlier method)

`scoring.method: ranksum` ranks the sub-KHG with the method of the earlier slide ([../docs/prior_method.md](../docs/prior_method.md)); the default is `need`. Both are always computed, so the two can be compared on the same sub-KHG: `peringkat_need` and `peringkat_ranksum` are in every output, and `laporan.json` has `ranking_agreement` (Spearman and the overlap of the top 20%). `scoring.method` only decides which one sets `kelas` and `peringkat`.

**What the rank means.** For choosing where to intervene first, rank 1 is the sub-KHG with the highest priority. So each indicator ranks the sub-KHG with the **worst condition first**: lowest NDMI, lowest NDVI, lowest water balance, largest storage decline, most months in deficit, longest dry runs, most hotspots. Thicker peat also ranks first (more at stake). The total score is the sum of rank x weight, and the **lowest total is the top priority**: the sub-KHG that is near the top on every indicator. The slide words seven of the eight directions the other way round ("higher NDMI, smaller rank number"), which would put the best-conditioned sub-KHG first; that is probably a wording choice, and the direction is to be confirmed with the team.

| Indicator | Column | Rank 1 is the |
|---|---|---|
| NDMI | `u_ndmi` | lowest |
| NDVI | `u_ndvi` (Sentinel-2, fetched with NDMI) | lowest |
| Peat depth | `i_peat_depth` | highest |
| Storage decline % | `u_storage_decline_pct` (neraca air module, not built) | highest |
| Water balance, daily mean | `u_wb_daily_mean` (neraca air module, not built) | lowest |
| Months in deficit | `u_deficit_months` | highest |
| Dry days, mean run | `u_dry_days_mean` (needs `sources.era5.enabled: true`) | highest |
| Hotspots | `u_hotspot` | highest |

- Ranks are 1 to n within each KHG (`normalise_scope: khg`), ties share the average rank. `skor_ranksum` is the sum as on the slide; `skor_ranksum_rel` rescales it to 0-1 so KHG with different numbers of sub-KHG compare. `rk_<indicator>` columns hold the single ranks, so each total can be checked by hand.
- Only the indicators that exist are used. A sub-KHG missing one is scaled up to the full weight, and `cakupan_ranksum` says how much of the weight was available. The log lists the indicators that were skipped.
- Weights are 1 each. Change them with `scoring.ranksum_weights: {u_hotspot: 2, u_ndvi: 0}` (0 drops one) and flip a direction with `scoring.ranksum_directions`. `scoring.ranksum_columns: {u_deficit_months: u_deficit_months_dry}` ranks another column in place of a slide indicator (the neraca air module counts 5 dry months, not 12).
- A rank sum ignores how large the differences are. An indicator that is almost constant inside a KHG (the rainfall and water-balance ones, from 4-25 km data) gets the same weight as NDMI. On the Riau test KHG, `u_deficit_months` took only the values 2 and 3 across 49 sub-KHG, yet it fills a full 1-49 rank spread. Treat those indicators with care until the neraca air module gives sub-KHG resolution.
- The weight-sensitivity runs are for the `need` score only and are skipped when the method is `ranksum`.
- On the Riau test KHG (only NDMI, NDVI and months in deficit available) the two methods agreed moderately: Spearman 0.61, 6 of the top 10 shared. That says little about which is right; it shows they are not interchangeable.

## Adding an analysis (e.g. neraca air)

The neraca air module exists (`repeat-neraca/docs/bucket_experiments_README.md`) but **failed its skill check on the first real KHG**, so its outputs have no weight in the need score; they are merged and available to the rank-sum, flagged by `neraca_skill_ok`.

Another analysis plugs in by returning a table with a `unit_id` column and indicator columns (`u_*`, `i_*`, `f_*`). Two ways:

- **A file.** List CSV or vector files in `extra_indicators:` in the config. They are joined on `unit_id` after the indicators are computed.
- **A function.** `pipeline.main(..., extra_indicators=[fn])` with `fn(cfg, khg_id, units, grid, cache) -> DataFrame`, called once per KHG.

A column with the same name as a computed one replaces it, so a finer water balance can replace `u_wb_mean`. A new indicator is scored once it has a weight. Its group defaults to its prefix and its direction to higher = more need:

```yaml
extra_indicators: [${REPEAT_KHG}/<code>_<name>/03_neraca/runs/<run>/neraca_unit.csv]
indicators:
  u_nab_deficit: {weight: 2.0}                # group u (need), higher = more need
  f_something:   {weight: 1.0, direction: -1}
```

Units with no row in the table get no value for that indicator, and the group score uses the rest. The log says how many are missing.

## Checks

- **Correlation.** Spearman between indicators; pairs above 0.8 are flagged. Expect NDMI and non-forest share to move together.
- **Sensitivity.** 300 runs perturb weights and α. Per unit: `p_kebutuhan_tinggi` (share of runs in the top need class), `p_top_risiko`, `sd_peringkat`.
- **Validation.** Indicators use 2015–2022. The ranking is tested on burned area and hotspots in 2023 (AUC, capture of the top 20%, Spearman), compared with urgency alone and with fire history alone.

With 6–30 units per KHG, treat the tertiles and validation as indicative.

## Outputs (`var/out/`)

`unit_prioritas.gpkg` / `.csv` (every unit: indicators, normalised `n_*`, group scores, `kelas`, `peringkat`, sensitivity), `kebutuhan_sekat.csv` (blocks needed, existing and additional per KHG and class), `peta_prioritas_<khg>.png`, `ringkasan_kelas.csv`, `korelasi_indikator.csv`, `laporan.json`.

## Status

- Tested on synthetic data and, for delineation, on the Pulau Padang LiDAR DTM (`repeat-delineation/examples/pulau_padang/`). The need ranking has only run on synthetic indicator tables. The cloud fetchers have not been run on live data.
- Not built: choosing the measure per ranked sub-KHG (sekat kanal / sumur bor / pompa). Criteria to start from are in Permen LHK 7/2022.
