# prioritas_khg: rewetting prioritisation for KHG, in Python

Two separate programs answer two different questions about peat rewetting. They share one data and indicator engine (`common/`) but have their own entry point, scoring and README.

| | **National** (`national/`) | **Sub-KHG** (`subkhg/`) |
|---|---|---|
| Question | Which KHG should get attention? | Inside a KHG, which sub-KHG needs the most intervention (sekat kanal, sumur bor, pompa)? |
| Run | `python -m national.run` | `python -m subkhg.run` |
| Unit | one unit per KHG | sub-KHG delineated automatically from the DTM, or hexagons, or your polygons |
| Grid | 250 m | 30 m |
| Layers | Coarse, wall-to-wall: climate, burned area, hotspots, peat depth, protected peat, canal density. No Sentinel-2, no feasibility. | Everything: NDMI, DTM, canal reach, pumping lift, metrik IPG, tidal zone, concessions |
| Ranking | Risk tertiles: Fokus nasional tinggi / sedang / rendah | **Need** tertiles: Kebutuhan intervensi tinggi / sedang / rendah. Feasibility is reported but does not change the rank. |
| Scoring code | `common/scoring.py` | `subkhg/prioritise.py` (reuses the shared normalisation, sensitivity and validation) |
| Details | this README | [subkhg/README.md](subkhg/README.md) |

```
configs/    example configs (national, subkhg), small smoke-test configs (configs/smoke/), your own go in configs/local/. The real-site configs (Kampar - Gaung, Sugihan - Lumpur) are in the hub: re-peat/sites/<khg>/
docs/       data_sources.md: providers (incl. BMKG), what was tested, ERA5 notes; prior_method.md: the team's earlier rank-sum method
            the real-data runbooks and reports moved to the hub: re-peat/sites/<khg>/
tests/fixtures/  small test inputs: KHG polygons and a prefetched 2021 cache for one KHG
common/     the prioritisation engine: indicators, scoring functions, pipeline. Grid, sources, tma and htmlkit now live in the repeat-common repo (import repeat_common); docs/data_sources.md lists the providers
national/   run.py                                national entry point and preset
subkhg/     run.py                                sub-KHG entry point and preset
            prepare_inputs.py                     clip the national vector files to one KHG: python -m subkhg.prepare_inputs
            prioritise.py                         need ranking (score_need)
            README.md                             full description of the sub-KHG program
(neraca air is the repeat-neraca repository; its sub-KHG table joins here through extra_indicators)
scripts/                                          one-question tools behind the numbers in docs/ (see scripts/README.md)
tests/                                            checks that need no data: python -m tests.test_ranksum
data_local/                                       your clipped copies of big inputs and the derived data of a run (not tracked)
```

How the pieces connect:

```
national.run ─► common.pipeline ─► common.scoring.score ─► KHG ranking, khg_terpilih.gpkg (top KHG)
                                                                  │
                                                  chosen KHG ─────┘  (the `khg` input of a sub-KHG run)
                                                                  ▼
subkhg.run ───► common.pipeline ─┬─ subkhg_units.gpkg (repeat-delineation) ─► sub-KHG polygons
                                 ├─ common.indicators.compute    ─► indicators per sub-KHG
                                 └─ subkhg.prioritise.score_need ─► need ranking
                                 + extra indicator tables (files or functions, e.g. neraca air from the repeat-neraca repository)
```

The stages exchange files: the `repeat-delineation` repository writes `subkhg_units.gpkg`, which a run here reads as `units: {mode: vector}`. Other analyses add indicator columns by `unit_id` (`extra_indicators`, see [subkhg/README.md](subkhg/README.md)).

`common.pipeline.main` takes the program-specific steps as hooks (`delineate`, `score`), so each program only supplies what is different. Changing one program does not change the other.

It is the Python alternative to a GEE workflow: layers are read from cloud-native sources (STAC + COG/Zarr), so only each KHG's window is transferred, and every step runs locally.

## National profile from local layers

`python -m national.profile` and `python -m national.dashboard` profile and rank all 865 KHG from the vector layers in `REPEAT_DATA` (burned area, VIIRS hotspots, canals, structures, villages, peat depth, SiTMAT), with no cloud fetch, and write an interactive dashboard (D3, vendored in `national/assets`). They reuse `common.scoring`. Method, decisions and commands: the hub's `docs/15-national-profile.md`; config: `configs/examples/national_profile.yaml`; test: `python -m tests.test_national_profile`.

## Investigations

`python -m investigations.airport --config configs/investigations/banjarbaru.yaml` writes a one-page report on fire near an airport and the KHG around it (runway against the KHG, peat from three sources, hotspots and burned area split into peat soil, mineral soil and outside the KHG, and the airport's METAR visibility, smoke and wind). Output: `${REPEAT_WORK}/investigations/banjarbaru.html`; `--reassemble` reuses the data. Inputs come from `repeat_common.fetch_klhk_peat`, `fetch_peat_extent --extra` and `fetch_metar`.

## Sub-KHG program

Delineation, the need ranking and its indicators are described in [subkhg/README.md](subkhg/README.md). The sections below describe the shared engine and the national ranking. Where the sub-KHG program differs, they say so.

## Shared engine and national scoring

The diagram shows the full flow. Up to the group scores the two programs are identical. The sub-KHG program replaces the last scoring steps (risk, classes) with its need ranking.

### Algorithm

```
KHG boundary ─► units (1 km² hexagons, or your sub-KHG polygons)
      │
      ├─ cache per KHG on a 30 m UTM grid (fetched once, reused)
      │     annual: NDMI, burned area, water deficit, dry spells
      │     static: land cover, surface water;  points: FIRMS hotspots
      │     plus your vectors/rasters: canals, rivers, peat depth, DTM, protected peat, TMA
      │
      ├─ indicators per unit, from BASELINE years only
      │     urgency u_*   impact i_*   feasibility f_*
      │
      ├─ robust 0–1 normalisation across all KHG (5th–95th percentile)
      ├─ group scores = weighted mean of available indicators (weights or AHP)
      ├─ risk = α·urgency + (1−α)·impact          (α = 0.6)
      ├─ classes: risk tertiles × feasibility tertiles
      │
      └─ checks: indicator correlation · weight sensitivity · validation on held-out years
```

### Indicators

In the national run the indicator groups are urgency (`u_`), impact (`i_`) and feasibility (`f_`). The sub-KHG program regroups some of them (canal reach, distance to water, forest share); see [subkhg/README.md](subkhg/README.md).

| Code | Meaning | Source (default) | Direction |
|---|---|---|---|
| `u_deficit` | Dry-season climatic water deficit (mm), mean of baseline years | TerraClimate `def` (Planetary Computer Zarr) | ↑ urgent |
| `u_wb_mean` | Mean monthly water balance P(1 − interception)(1 − C) − ET (mm) | TerraClimate `ppt`, `aet` + WorldCover interception | ↓ urgent |
| `u_deficit_months` | Months per year with negative water balance | same | ↑ |
| `u_deficit_elnino` | Same, El Niño years only | TerraClimate | ↑ |
| `u_ndmi` | Median dry-season NDMI (Aug–Oct composite) | Sentinel-2 L2A (STAC), SCL cloud mask, BOA offset corrected | ↓ urgent |
| `u_ndvi` | Median dry-season NDVI (weight 0; used by the rank-sum method) | Sentinel-2 L2A (B8A, B04), same scenes as NDMI | ↓ urgent |
| `u_dry_days_mean` | Mean length of the dry runs (weight 0; used by the rank-sum method) | ERA5, or CHIRPS | ↑ |
| `u_dryspell` | Longest run of dry days (< 1 mm) in the dry months | ERA5 hourly rainfall (Google ARCO-ERA5), or CHIRPS | ↑ |
| `u_spell14` | Number of dry spells ≥ 14 days in the dry months | same | ↑ |
| `u_fire_freq` | Mean share of years burned | MODIS MCD64A1, or your dNBR/KLH maps | ↑ |
| `u_hotspot` | Hotspots per km² per year | FIRMS VIIRS (nominal/high confidence) | ↑ |
| `u_canal_density` | Canal length per km² | your canal layer | ↑ |
| `u_tma` | Share of logger days with water table deeper than 0.4 m, mean over the stations in the unit | SiTMAT extract or your TMA CSV (see below) | ↑ |
| `u_tma_recession` | Mean dry-period water-table decline (mm/day), intervals where it rose ignored | same | ↑ |
| `u_ipg_gap` | 1 − metrik IPG; IPG = existing blocks ÷ blocks needed, spacing = 0.4 m ÷ canal slope | canals (+ class), DTM, existing blocks | ↑ |
| `i_peat_depth` | Mean peat depth | your raster | ↑ important |
| `i_water_stock` | Peat water stock (m): thickness × 0.8, or × 0.7 within canal reach | peat depth + canals | reported, weight 0 by default |
| `i_protected` | Share in protected-function peat (lindung) | your vector | ↑ |
| `i_exposure` | Share within 2 km of settlements | your vector | ↑ |
| `i_forest` | Share of remaining forest / mangrove | ESA WorldCover | ↑ |
| `f_reach` | Share within canal influence distance (200 m; 60 m on burnt peat) | canals + burned area | ↑ feasible |
| `f_water_dist` | Mean distance to dry-season water (JRC seasonality ≥ 10 months, RBI rivers/lakes) | JRC GSW + your vectors | ↓ feasible |
| `f_lift` | Median height above the nearest water source (pumping lift proxy) | `dtm_smooth.tif` from the `demnas-corrections` repository | ↓ feasible |
| `f_access` | Mean distance to roads | your vector | ↓ feasible |
| `v_burned_frac`, `v_hotspot` | Burned share and hotspot density in **validation** years | same sources | targets only |

Water balance and IPG parameters come from the team's Kahayan–Sebangau study (2021): interception from 0 % (open land) to 16.4 % (forest), runoff coefficient 0.07–0.18 measured on Pulau Padang (default 0.12), water content 0.8 / 0.7, design water-table limit dA = 0.4 m. The water-stock indicator is total water, not drainable water: only the specific-yield part drains as the water table falls.

Extra unit attributes (not scored): `tidal_share`, `pengelola` (dominant concession type or "Non-konsesi"), `porsi_dikecualikan`, `kemiringan_kanal`, `n_sekat_ada`, `n_sekat_perlu`, `sekat_tambahan`, `n_tma_stations` (water-table stations in the unit; 0 when none).

Missing indicators don't break a unit: each group score is the weighted mean of what's available, and `cakupan_*` columns report how much of the weight was covered. Indicators available for fewer than 20 units (e.g. sparse TMA loggers) are reported but not scored.

### Classes (national run)

| Risk \ Feasibility | Low | Medium | High |
|---|---|---|---|
| **High** | Siaga pemadaman | Prioritas 1: pembasahan | Prioritas 1: pembasahan |
| **Medium** | Pantau dan rencanakan | Pantau dan rencanakan | Prioritas 2: pembasahan |
| **Low** | Pantau | Pantau | Pantau |

The risk × feasibility table above is the shared scoring (`common.scoring.score`). The sub-KHG program does not use it and classes by need instead. Tertiles are computed across all KHG, or set fixed thresholds in `scoring.fixed_thresholds`. Two override classes, which the sub-KHG program also applies:

- **Pengaruh pasang surut: pantau**, when `scoring.tidal_mode: exclude` and at least half the unit is tidal. The default `downweight` instead reduces urgency by 70 % × tidal share.
- **Dikecualikan (pengelolaan lahan)**, when at least half the unit is a concession type listed in `vectors.concessions.exclude_types` (default IUP).

In the national run (`scoring.national: true`) the classes are **Fokus nasional: tinggi / sedang / rendah** (risk tertiles).

`scoring.normalise_scope: all` compares units across every KHG in the run. Use `khg` to rank within each KHG separately, for example when each KHG has its own budget.

### Checks

- **Correlation.** Spearman between normalised indicators; pairs above 0.8 are flagged as possible double counting (e.g. deficit and dry spells often move together).
- **Sensitivity.** 300 Monte Carlo runs perturb weights (Dirichlet around your weights) and α. Per unit you get `p_prioritas1` (share of runs in Prioritas 1; `p_kebutuhan_tinggi` in the sub-KHG program), `p_top_risiko` and `sd_peringkat`.
- **Validation.** Indicators use baseline years only (shared default 2016–2022; the sub-KHG program starts in 2015). The ranking is then tested on burned area and hotspots in the held-out year(s) (default 2023):
  - AUC;
  - share of validation burned area captured by the top 20% of units (random = 20%);
  - Spearman correlation.

  The same metrics are computed for urgency alone and for fire history alone, so you can show what the method adds over "where it burned before".

## Run

```bash
pip install -r requirements.txt     # or: uv pip install -r requirements.txt
mkdir -p configs/local
# national: which KHG?
python -m national.run --print-default-config > configs/local/national.yaml
python -m national.run --config configs/local/national.yaml        # writes khg_terpilih.gpkg (top KHG)

# sub-KHG: which sub-KHG inside the chosen KHG?
# first, in the repeat-delineation repo: python -m repeat_delineation --config <delineate.yaml>   (writes subkhg_units.gpkg; check the polygons)
python -m subkhg.run --print-default-config > configs/local/subkhg.yaml     # edit paths and years
python -m subkhg.run --config configs/local/subkhg.yaml                     # fetch missing layers, score
python -m subkhg.run --config configs/local/subkhg.yaml --fetch-only        # just build the cache
python -m subkhg.run --config configs/local/subkhg.yaml --skip-fetch        # re-score from cache (e.g. new weights)
```

Run from the repo root. Both programs accept `--config`, `--khg`, `--out`, `--fetch-only` and `--skip-fetch`. `configs/examples/national.example.yaml` and `configs/examples/subkhg.example.yaml` hold the defaults of each program; put your own in `configs/local/` (not tracked). Set `khg` in the sub-KHG config to `khg_terpilih.gpkg` to continue from the national shortlist.

`params.peat_depth_scale` turns the peat depth raster into metres (default 1). A raster in centimetres needs `0.01`; the water stock indicator is in metres.

Minimal config:

```yaml
khg: data/khg_sample8.gpkg
khg_id_field: khg_id
units: {mode: hex, hex_area_km2: 1.0}       # or {mode: vector, path: data/sub_khg.gpkg}
years: {baseline: [2016, 2022], validation: [2023], elnino: [2015, 2019, 2023]}
vectors:
  canals: data/kanal.gpkg
  rivers: data/rbi_sungai.gpkg
  settlements: data/rbi_permukiman.gpkg
  protected: {path: data/fungsi_ekosistem_gambut.gpkg, field: fungsi, values: [lindung]}
  blocks: data/sekat_kanal_existing.gpkg    # for metrik IPG
  tidal: data/zona_pasang_surut.gpkg
  concessions: {path: data/konsesi_iup.gpkg, type_field: jenis, exclude_types: [IUP]}
tma: {path: ../sitmat-extract/sitmat_out/processed}     # water table, see "Water table (TMA)" below
rasters:
  peat_depth: data/kedalaman_gambut.tif
  dtm: out_dtm/dtm_smooth.tif
```

For the operational ranking (rather than validation), set `baseline` to include the latest year and leave `validation` empty or set to a year you only want for reporting.

### Water table (TMA)

`common/tma.py` turns the input into one table (`station_id, date, depth_m, lon, lat`, depth positive below the surface), and `indicators.py` only reads that table. `tma.path` picks the format:

- **A folder: SiTMAT extract** (the `sitmat_out/processed/` folder of the sitmat-extract project: `daily_long.csv` + `stations.csv`, and `stations_geo.csv` if present). `water_level_cm` is negative below the surface, so `depth_m = -cm / 100`.
- **A file: CSV** with `station_id, date, wtd_m, lon, lat`. Set `params.tma_depth_positive` to say how the sign works. Left unset, the absolute value is used and a warning is logged, which counts flooded readings as deep.

```yaml
tma:
  path: ../sitmat-extract/sitmat_out/processed
  kinds: [concession]            # add "community": low coverage, many flagged values
  drop_flags: [range, spike]     # QC flags from the extract
  min_coverage: 0.5              # valid readings on at least this share of the days in the period
  period: null                   # [start, end]; default: all dates (SiTMAT) or the baseline years (CSV)
```

- Stations with bad coordinates ((0,0), lat = lon, outside Indonesia, `has_loc = 0`) are dropped.
- SiTMAT covers one season (2026-04 to 2026-10 at the time of writing), after the validation year. Treat `u_tma` as the current state of the water table, not a baseline-year indicator; the held-out validation does not test it.
- A reading counts as exceeding when the water table is deeper than `params.tma_threshold_m` (0.4 m). The portal's own status class `ORANYE` also includes readings of exactly −40 cm (about 6% of readings), so its shares of days below −40 cm are higher than `u_tma`.
- Stations are assigned to a unit by location. Most units have none: SiTMAT stations are mostly inside concessions, so coverage is uneven. Units without a station get no `u_tma`; `n_tma_stations` and the log show the coverage. An indicator available for fewer than 20 units is reported but not scored.
- The concession data has no rainfall or soil moisture. Rainfall for a water balance comes from ERA5 (see docs/data_sources.md).

### Using your own layers instead of the cloud

Every source has a `local` key, for example:

```yaml
sources:
  burned: {local: "data/dnbr/burned_{year}.tif"}     # any value > 0 = burned
  ndmi:   {local: "data/ndmi/ndmi_{year}.tif"}
  firms:  {local: "data/firms/viirs_indonesia_2015_2023.csv"}
```

Local files are reprojected to the KHG grid. Files already in `cache/<khg_id>/` are never refetched, so you can also drop prepared GeoTIFFs there directly.

### Weights and AHP

Change weights per indicator (`indicators: {u_fire_freq: {weight: 3}}`), disable one (`enabled: false`), or give a pairwise matrix per group:

```yaml
ahp:
  u:
    indicators: [u_fire_freq, u_deficit, u_ndmi]
    matrix: [[1, 3, 3], [0.333, 1, 1], [0.333, 1, 1]]
```

The consistency ratio is reported; above 0.10 triggers a warning.

### A real-data run

`re-peat/sites/kampar_gaung/README.md` (the hub) is the worked example: Sungai Kampar - Sungai Gaung, from clipping the inputs to the report, with
the commands, the settings and why each was chosen. Its configs use `${REPEAT_DATA}` and `${SITMAT_PROCESSED}` for data kept
outside the repo: `${NAME}` in any config value is replaced by the environment variable, and a missing variable stops with a
message. Every analysis behind a number in the docs is a command in the repo (see `scripts/README.md`), not a throwaway.

### Smoke tests

Each program runs on its own on the small inputs in `tests/fixtures/`. Outputs go to `var/out/smoke/`, which git ignores.

```bash
python -m subkhg.run --config configs/smoke/subkhg.yaml --skip-fetch                # 49 hexagons in a Riau KHG, from the prefetched cache, ~10 s
python -m national.run --config configs/smoke/national.yaml                         # 3 small KHG, fetches the 2021 layers, ~2 min
```

All three ran on 2026-10-15. The sub-KHG smoke test has no canals, peat depth or roads, so only a few indicators are scored: it checks that the pipeline runs, not that the ranking is right.

## Outputs (`out/`)

Both programs write the same set of files, with the ranking columns of their own scoring.

| File | Content |
|---|---|
| `unit_prioritas.gpkg` / `.csv` | Every unit: raw indicators, normalised `n_*`, group scores, `skor_risiko`, `kelas`, `peringkat`, sensitivity fields, validation targets. In the sub-KHG program `skor_risiko` is the need score and `kelas` the need class. |
| `khg_terpilih.gpkg` | National run: top KHG (`scoring.top_n`) |
| `kebutuhan_sekat.csv` | Sub-KHG run: blocks needed, existing and additional per KHG and class (first cost estimate) |
| `peta_prioritas_<khg>.png` | Urgency, impact, feasibility and class maps per KHG |
| `ringkasan_kelas.csv` | Units and km² per class per KHG |
| `korelasi_indikator.csv` | Spearman matrix |
| `laporan.json` | Weights, AHP consistency, thresholds, class counts, correlated pairs, sensitivity, validation, indicator coverage, config |

## Status of the code

- **Tested on synthetic data**: six KHG in the national run (ranking followed the built-in risk intensity) and sub-KHG delineation, IPG, tidal and concession handling in the sub-KHG run (12 and 11 sub-KHG per KHG, bounded by divides and primary canals; see `contoh_subkhg_sintetis.png`). The sub-KHG need ranking has only run on synthetic indicator tables. Delineation was also tested on the Pulau Padang LiDAR DTM. With a known fire-risk field, the top 20% of units captured 64% of held-out burned area (random would be 20%). Urgency alone reached AUC 0.79, above fire history alone at 0.77.
- **Live fetch test (one small KHG, year 2021):** Sentinel-2 NDMI, MODIS burned area, TerraClimate, WorldCover, JRC water and FIRMS work. CHIRPS failed with HTTP 403, so rainfall now comes from ERA5 (note in docs/data_sources.md). TerraClimate on Planetary Computer ends in 2021, so 2022–2023 have no deficit. Details, fixes and other providers: [docs/data_sources.md](docs/data_sources.md). Every source fails independently, logs why, and can be replaced by a local file.
- **Coarse climate layers.** TerraClimate (~4 km) and ERA5 (~25 km) are much coarser than 1 km² units. They separate KHG and large zones, not neighbouring hexagons. Fine-scale contrast comes from NDMI, fire, canals and peat depth.
- **FIRMS country files** are large; for many runs, download them once and point `sources.firms.local` at the file.
