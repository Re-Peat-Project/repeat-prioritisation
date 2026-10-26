# Scripts

Small command-line tools that answer one question each. They are how the numbers in `docs/` were obtained, so anyone can
repeat them. Run them from the repo root with the project environment (`PYTHONPATH=.` if a script imports `common`).

| Script | Question | Where its result is used |
|---|---|---|
| `probe_cloud_sources.py catalogue` / `coverage` | Which cloud datasets exist, and do they cover our years? (TerraClimate ends 2021-12, Planetary Computer ERA5 stops at 2020-12, the ARCO-ERA5 store reaches within days of today) | `docs/data_sources.md`, providers and date coverage |
| `bmkg_catalogue.py list` / `layer` | What does BMKG publish as data (HTH, fire danger, drought code)? What do the layers hold at a point? | `docs/data_sources.md`, BMKG section |
| `check_tma_vs_sitmat.py` | Does our SiTMAT reader agree with the sitmat-extract project's own summary? | README, water table (TMA) |
| `check_era5_vs_terraclimate.py` | How close is ERA5 to TerraClimate for one month of one KHG? | `docs/data_sources.md`, fallback for the TerraClimate gap |
| `forcing_test.sh <khg>` (moved to repeat-neraca, retired with the bucket experiments 2026-10-26) | Does finer rain (CHIRPS v3, 5 km) or evaporation (WaPOR v3, 300 m) than ERA5 improve the neraca air calibration? Then `python -m repeat_neraca.bucket.forcing_compare` tabulates the runs | `repeat-neraca/docs/bucket_reports/<khg>_forcing_test.md`, `repeat_neraca.bucket/README.md` |
| `index_repeat_data.py` | Which DTM and peat depth rasters cover which KHG boundary? | `re-peat/sites/14.02-04-05.01_kampar_gaung/README.md`, step 0 (`re-peat/sites/repeat_data_index.csv`) |

The checks that belong to a particular run are commands of the packages, not scripts: `repeat-subkhg-check`
(the inputs of a run), `python -m repeat_neraca.stations` (repeat-neraca) (the station files for the neraca air deficit; the bucket experiments `export_inputs`, `covariates`, `sentinel1` and `radar_temporal` were retired 2026-10-26, their reports are in `repeat-neraca/docs/bucket_reports/`) and
`repeat-subkhg-report` (the report of a run). The tests that need no data are in `tests/`.

Two notes for anyone extending this:

- The cache of a run (`<cache_dir>/<khg_id>/`) is keyed by file name, not by the settings that made the file. After changing a
  setting that changes a layer (for example `sources.ndmi.res_m`), delete the old layer files, or the old ones are reused.
- CHIRPS (data.chc.ucsb.edu) refuses clients that read many files at once with HTTP 403, even for a plain HEAD request, for hours. `repeat_common.forcing` reads two files at a time, keeps every day on disk and stops with an error instead of returning NaN. Do not parallelise it.
- BMKG's servers answer `curl` and refuse Python's `urllib` (HTTP 403); `bmkg_catalogue.py` calls curl for that reason.
