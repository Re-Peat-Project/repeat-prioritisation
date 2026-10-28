# Data sources

What the pipeline reads from the cloud today, what was checked live, and what else is available or needed. Checked on 2026-10-15 from this machine, with the packages in `requirements.txt` installed in `.venv`. "Not tested" means it was found in a catalogue or documentation but never read.

## Live fetch test (`--fetch-only`, one small KHG in Riau, year 2021)

| Source | Result |
|---|---|
| Sentinel-2 NDMI (Planetary Computer, STAC + odc) | Works. 98% valid, median 0.32. NDVI from the same scenes (added 2026-10-16): median 0.71, correlation with NDMI 0.53. |
| MODIS burned area (`modis-64A1-061`) | Works. All zero in this KHG for 2021, which may be true. |
| TerraClimate deficit and monthly rain and ET (Zarr) | Works **after two fixes** (below). `deficit` is 0 everywhere here: the KHG is very wet (monthly rain 111–401 mm), so the dry-season deficit gives no signal in perhumid areas. |
| ESA WorldCover, JRC surface water | Work. |
| FIRMS hotspots (country CSV, 5 MB per year) | Works. 0 points: the 3 points in the KHG bounding box lie outside the polygon. |
| CHIRPS dry spells (daily COGs from `data.chc.ucsb.edu`) | **Fails.** HTTP 403. Replaced by ERA5, which works (next section). |

Fixed in `common/sources.py`: `xr.open_zarr` was called with `storage_options` twice and with an `engine` argument the current xarray rejects. Each raised a `TypeError` that the fetcher's generic `except` would have turned into "deficit unavailable". It now uses `xr.open_dataset(href, **open_kwargs)`, the pattern in the Planetary Computer asset.

## Rainfall: ERA5 replaces CHIRPS (decision, 2026-10-15)

`u_dryspell` and `u_spell14` now come from **ERA5 hourly precipitation** (Google ARCO-ERA5, public Zarr, no account), because CHIRPS blocked us. CHIRPS is still in the code: set `sources.era5.enabled: false` and `sources.chirps.enabled: true`. If both are on, ERA5 is used.

What changed for the indicators:

- **Dry months only.** CHIRPS computed the spells over the whole year. ERA5 reads only the dry months (`dry_months`, default Jun–Oct, or `sources.era5.months`), because the store makes every hour cost a network read. Spell counts and longest runs are therefore not comparable with earlier CHIRPS values.
- **Coarser.** 0.25° (about 25 km) against 0.05° for CHIRPS. A 4,000 ha KHG falls in 2×3 cells. The indicator separates KHG, not neighbouring sub-KHG. It was already almost constant across sub-KHG with CHIRPS.
- **Threshold.** Dry day = daily total below `era5.dry_day_mm` (1 mm). Reanalysis rain tends to fall too often at light intensity in the tropics (drizzle bias), which shortens dry spells. I have not compared ERA5 with gauges or CHIRPS here, so treat the 1 mm threshold as unchecked and consider a higher one.
- **UTC days.** A day is the 24 hourly values from 01:00 to 24:00 UTC. Indonesian local days (WIB, UTC+7) start 7 hours earlier.
- **Cost.** The store holds one hour of the whole globe per chunk, so each hour is about 0.3 s whatever the window. One KHG-year of dry months (153 days) took **about 4 minutes** with 8 parallel readers; nine years would take about 35 minutes per KHG. Reads are shared by all KHG in principle (a window covering all of them costs the same as one), but the cache is built per KHG, so this is not exploited yet.
- **Load limits.** Google answered HTTP 503 to 16 parallel readers, so the default is 8 with up to 6 retries (waits of 1, 2, 4 ... s). That is the same burst sensitivity as CHIRPS: do not raise `workers` much.

Check against TerraClimate (the same cell, 2021, Jun–Oct): ERA5 gives about 887 mm (5.8 mm/day), TerraClimate 881 mm. Result for the test KHG: longest dry run about 11 days, no 14-day spells.

### Fallback for the TerraClimate gap (decision, 2026-10-15)

The same store holds evaporation, potential evaporation and soil water, and runs past 2023. For years TerraClimate does not cover (2022 on), the fetcher now fills `deficit_<year>.tif` and the monthly `climate/ppt_<year>.tif` and `aet_<year>.tif` from ERA5. TerraClimate stays the source for 2015–2021. Switch it off with `sources.deficit.fallback: null`; it also needs `sources.era5.enabled`.

- **ppt** = monthly sum of hourly rain. **aet** = ERA5 evaporation (the monthly mean of every 3rd hour, scaled to the month: evaporation is smooth through the day). **deficit** = sum over the dry months of max(ERA5 PET − aet, 0).
- **The two sources are not interchangeable.** For August 2021 on the Riau test KHG (a year TerraClimate covers): evaporation 113 mm (ERA5) against 112 mm; rain 224 mm against 184 mm (ERA5 about 20% higher); deficit 11 mm against 0. So the 2022–2023 values are not on the same scale as 2015–2021 for rain and deficit. An indicator averaged over years mixes them. Treat the fallback as a way to have some value rather than none, and prefer per-year comparisons within one source if it matters.
- **Cost.** A full year is about 13,000 hourly reads. The 2022 test on the Riau KHG took **18 minutes** for deficit, ppt and aet, and 22 minutes with the dry-spell layers (annual rain 2,797 mm, plausible for Riau). A single month takes about 90 seconds.
- **National run only, by default.** The sub-KHG preset turns ERA5 off (its rainfall indicators have weight 0), so the fallback and the dry-spell layers are fetched only by the national run. That does not scale as built: the national run reads each KHG separately, so about 180 KHG × 20 minutes × the gap years is days of reading, although one window over all of Indonesia would cost the same 13,000 reads as one KHG. A shared regional read is the next fix.
- Wherever the fallback is used, the log says "from ERA5 (TerraClimate fallback)".

Planetary Computer's own ERA5 (`era5-pds`) is not an option: it has items only to 2020-12 and no evaporation.

Open problems:
- **CHIRPS 403** (no longer used by default; on 2026-10-16 a HEAD request for files of 2022 to 2024 returned 200 again, so the block looks temporary; reads of the files were not retried). The first requests (HEAD) worked, then a full-year fetch (365 files, 8 workers) got 403s. Afterwards every file on the host, including ones that had answered 200, returned 403, even to plain `curl`. That looks like a block triggered by the request burst. It may be temporary; it was not retested after that. The loader needs a lower concurrency, retries with back-off, and a per-day cache.
- **TerraClimate ends 2021-12** on Planetary Computer. The baseline runs to 2022 and the validation year is 2023, so `u_deficit`, `u_wb_mean` and the El Niño indicator silently use fewer years. The fetcher now logs a warning per missing year. ERA5 now fills these years (see the fallback section).
- Planetary Computer's dataset end dates matter for other collections too: `jrc-gsw` ends 2020, `gpm-imerg-hhr` 2021-05, `esa-worldcover` has 2020 and 2021 only.

How to repeat the checks on this page: `scripts/probe_cloud_sources.py` (catalogues and date coverage), `scripts/bmkg_catalogue.py` (BMKG layers), `scripts/check_era5_vs_terraclimate.py`, `scripts/check_tma_vs_sitmat.py`; see `scripts/README.md`.

## Providers

| Provider | Access | Useful here | Notes |
|---|---|---|---|
| **Microsoft Planetary Computer** (STAC) | Free, assets signed with `planetary_computer`. Used today. | Sentinel-2 L2A, Sentinel-1 RTC and GRD, Landsat C2, HLS, MODIS (burned area, fire, ET yearly, VI, LST), Copernicus DEM, NASADEM, ALOS PALSAR and forest/non-forest mosaics, WorldCover, Esri land cover to 2024, ERA5, TerraClimate | 139 collections. Sentinel-1 RTC returned 8 scenes for Aug 2023 over Riau (`vv`, `vh`). |
| **Earth Search (Element 84, AWS)** | Free, unsigned STAC | Sentinel-2 (L2A, collection 1), Sentinel-1 GRD, Landsat C2, Copernicus DEM | Only 9 collections. A fallback for Sentinel-2 if Planetary Computer is down. Not tested. |
| **Copernicus Data Space (CDSE) STAC** | Catalogue is open; asset access needs a free account (not tested) | Copernicus Land Monitoring Service products: burnt area 300 m monthly (2018 to now), evapotranspiration 300 m 10-daily (**only from 2025-11**), soil water index 12.5 km daily (2007 to now), LAI, FAPAR, NDVI, GPP, land surface temperature, water bodies 300 m; MODIS Terra MOD16A2GF 8-day ET mirror | 427 collections. Sentinel-1/2 are also here. |
| **NASA Earthdata** (CMR-STAC, Earthdata Cloud) | Free account; STAC endpoints respond (HTTP 200) | GPM IMERG daily (0.1°) and SMAP L4 soil moisture (9 km) | The IMERG and SMAP assets themselves were not read. |
| **Google ARCO-ERA5** (public Zarr bucket) | Free, no account (per its README, not tested) | ERA5 0.25° hourly: total precipitation, evaporation, volumetric soil water layers 1–4 | Reaches 2023 and later. ERA5-Land (0.1°) is on the Copernicus Climate Data Store, which needs a login. |
| **Direct HTTP** (CHIRPS, FIRMS) | Free | CHIRPS v2 daily COGs, FIRMS fire CSVs | CHIRPS blocked us (above). CHIRPS v3 exists (CHC site and Earth Engine). |
| **Google Earth Engine** | Free for research, needs an account | CHIRPS, ERA5-Land, MODIS ET and more | Not cloud-native in the STAC/COG sense; needs the `earthengine` API. Not tested. |

Indonesian sources, not cloud APIs: BIG (RBI rivers, settlements), the national peat maps and KHG boundaries, BRGM/PRIMS, SiTMAT (water table, see `common/tma.py`). Global peat extent: Global Peatland Map 2.0 (1 km GeoTIFF download).

## BMKG (Indonesian weather and climate agency), checked 2026-10-16

Short answer: BMKG's own HTH (hari tanpa hujan, consecutive days without rain) is published as maps, not as data. The numbers are in other places.

| BMKG source | What it holds | Usable here? |
|---|---|---|
| **Open Data portal** `data.bmkg.go.id` (JSON API `api.bmkg.go.id/publik/...`) | 3-day weather forecast per kelurahan or village, earthquakes, nowcast warnings | The API works (the forecast query returned JSON). No observations and no HTH, so not useful for the baseline. |
| **HTH monitoring** (`iklim.bmkg.go.id`, regional pages, per dasarian = 10 days) | Maps of consecutive dry days, in categories | **Images and dashboards only.** I found no download, shapefile or API. The climate site embeds Tableau dashboards (`visklim.bmkg.go.id`); I did not test exporting from them. |
| **Satellite "GSMaP Consecutive Dry Days"** (`inderaja.bmkg.go.id/IMAGE/GSMAP/GSMaP_HTH.png`) | A PNG map of dry days computed from daily GSMaP rainfall | Image only. BMKG requires citing it as the source, with its logo, and forbids cropping that drops them. The threshold and update rate are not on the page. |
| **Data Online** `dataonline.bmkg.go.id` | Station observations (daily rain and more) | Needs a free account and a CAPTCHA, so not scriptable. Terms and limits not checked. Stations are sparse in peat areas. |
| **BMKG GIS (ArcGIS Server)** `gis.bmkg.go.id/arcgis/rest/services` | 192 services; open, no token, queryable | See below: the fire-danger layers are the useful find. |

**Does BIG (Badan Informasi Geospasial) host BMKG's data? Checked 2026-10-16: not as far as I could reach.**
- `geoportal.big.go.id` (catalogue SIKAMBING, Swagger API at `/sikambing/api/`, no login needed for reads): its harvest count by organization lists one organization, BIG itself, with 428 records. No BMKG records.
- `onemap.big.go.id` (Kebijakan Satu Peta) names BMKG as a data custodian (walidata) of the national one-map policy, but the page holds no data links.
- `tanahair.indonesia.go.id` (Ina-Geoportal, the national spatial data network of about 470 nodes and 14,000 datasets) has a web app on an API at `/api-inageo/`, but no public documentation; the common endpoint names I tried returned 404. The network may list BMKG layers; I could not query it. Searching its web interface by hand ("curah hujan", "BMKG") is the quickest check.
- BMKG's own "Satu Peta MKG" (`gis.bmkg.go.id/portal`) is the ArcGIS server described below.

BMKG's GIS includes, under `Pusat_Meteorologi_Publik/`, the **Fire Danger Rating System** (observed `Observation_Index_...` and forecast): Drought Code (DC), Duff Moisture Code (DMC), Fine Fuel Moisture Code (FFMC), Buildup Index (BUI), Initial Spread Index (ISI) and Fire Weather Index (FWI). `Forecast_Index_Drought_Code` has day 0 to 7 forecasts. DC tracks the dryness of the deep organic layer, which is why it matters for peat. Also present: `Peta_Rawan_Kekeringan_Meteorologis` (meteorological drought-prone zones), monthly and dasarian rainfall analysis and forecasts, rainfall normals, and a daily AWS layer.

- **Values.** `gridcode` is the index value. Classes for DC: 0-141, 142-261, 262-350, over 351. Grid cells are about 0.008 degrees (observed) and 0.02 degrees (forecast DC), much finer than TerraClimate or ERA5.
- **Test on the Riau KHG:** forecast DC day 0 gave 22 cells with values 175-191; the observed DC layer had no cells there (observed BUI had 6, FWI 2), so the observed grid has gaps.
- **No history.** The layers carry no date field and no edit date I could read: they are latest-value snapshots. They can give a current state per sub-KHG, like the SiTMAT water table, but cannot fill baseline years 2015-2022. Archiving a snapshot each day would build a record over time. Freshness should be checked against BMKG's own portal before relying on them.
- **Access note.** BMKG hosts refuse Python's `urllib` (HTTP 403) but answer `curl` and browser-like clients; this is a client fingerprint, not an IP block. Use a polite request rate.

**HTH itself can be computed, not downloaded.** BMKG's satellite HTH is computed from daily GSMaP (JAXA's rainfall product, 0.1 degree, gauge-adjusted version in version 8 from 1998; free with registration on JAXA's server, and on Google Earth Engine). We already compute the dry-run indicators from ERA5 (`u_dryspell`, `u_spell14`, dry day under 1 mm). GSMaP would be a closer match to BMKG's HTH and is satellite-based like CHIRPS; it was not tested. The standard BMKG dry-day threshold is a daily rainfall under 1 mm; I could not confirm the categories from BMKG's own pages in this check.

## What the programs need that we do not have yet

| Need | Candidate | Caveat |
|---|---|---|
| Rainfall for 2022–2023 and a water balance | CHIRPS v2/v3 (5 km), ERA5 (25 km), IMERG (10 km) | **ERA5 is now the rainfall source.** IMERG on Planetary Computer ends 2021; NASA's copy needs a login. CHIRPS is blocked for now. |
| Evapotranspiration after 2021 | MODIS MOD16A2GF 8-day (500 m, via CDSE or NASA), ERA5 evaporation | TerraClimate `aet` ends 2021. The Planetary Computer MODIS ET is yearly only. |
| Soil moisture | SMAP L4 (9 km), CLMS SWI (12.5 km), ERA5 layers | Too coarse to separate sub-KHG. Useful per KHG. |
| Wetness at 10–20 m | Sentinel-1 RTC (VV, VH) | A published study found Sentinel-1 backscatter a possible proxy for peat water table depth, with reliability to be assessed (abstract only, not read in full). Untested here; a candidate, not evidence. |
| Land cover for 2022–2023 | `io-lulc-annual-v02` (to 2024) | WorldCover has 2020 and 2021 only. Class codes differ. |
| Ground model | Copernicus DEM 30 m | The team's DEMNAS-based DTM is the better input; use this as a check. |

Fire, burned area and NDMI are covered by the sources already in use.

## Plan for a common loader

The pieces below replace code that is currently copied:

1. **One STAC raster loader.** `ndmi_cloud`, `burned_cloud` and `static_cloud` each repeat search, `odc.stac.load` and reduce. One function takes catalogue, collection, bands, grid, time range, query and a reducer. A `provider` setting per source chooses Planetary Computer (signed) or Earth Search (unsigned).
2. **A Zarr helper** (TerraClimate, ERA5): open from an asset, select by box and time, resample to the grid.
3. **A polite reader** shared by ERA5 and CHIRPS: low concurrency, retries with back-off (ERA5 has these now, in `_retry`), a per-day cache on disk so an interrupted run resumes, and one read window for all KHG in a run.
4. **A date-coverage check** for every source: warn when requested years fall outside the dataset, as the TerraClimate fetcher now does.

No registry or plugin system. New datasets (ERA5, Sentinel-1) become one config entry and one reducer function each. Use the live catalogue (`client.get_collections()`) to confirm collection IDs; the lists above come from it.

## Finer rainfall, evaporation and water-management data (research, 2026-10-16)

Why: the neraca air test (runbook, Kampar-Gaung) has no spatial skill. ERA5 is 0.25 degrees (about 25 km), so the whole
KHG gets almost the same P and E, and the observed water tables look managed (weirs), not rain-driven. Two things could
help: forcing finer than 25 km, and information on how water is managed. Status: Sentinel-1 **tested** (see below); the rest **found, not yet tested or wired in**.

| Need | Candidate | Resolution | Access | Notes |
|---|---|---|---|---|
| Rain | CHIRPS v2/v3 | 5 km, daily | open HTTP / GEE | Blends gauges; already probed in `scripts/probe_cloud_sources.py` (availability varied) |
| Rain | GSMaP (JAXA) | 0.1 deg, hourly | free registration, GEE | Best Indonesian coverage of the microwave products |
| Rain | IMERG (NASA) | 0.1 deg, 30 min | Earthdata login | |
| Rain, E | ERA5-Land (CDS) | 0.1 deg, hourly | CDS account | 9 km: finer than ERA5 but still coarse against 130+ km2 units |
| Evaporation | MODIS MOD16A2GF v6.1 | 500 m, 8-day, 2000-2025 | Earthdata, GEE, AWS open data (MOD16A2) | Actual ET (Penman-Monteith logic); cloud gaps are filled in the GF version |
| Evaporation | FAO WaPOR v3 level 1 | 300 m, 10-day | FAO API, GEE | Global at level 1; documented for Africa and the Near East, check Indonesian quality before use |
| Wetness proxy | Sentinel-1 backscatter (Planetary Computer RTC) | 10-20 m, 6-12 days | STAC, no login | Studies relate SAR backscatter to peat water table depth (e.g. Sci. Total Environ. 2021, doi 10.1016/j.scitotenv.2020.143312); strength to be tested here against the 86 stations with the existing block cross-validation |
| Management | GFW oil palm and wood-fibre concessions | polygons | data.globalforestwatch.org | Says who manages the land, not where weirs are; drainage reaches up to 5 km outside plantations (HRW 2021) |
| Management | BRGM canal blocks, canals (have) | points, lines | `REPEAT_DATA` | 2,884 blocks in KHG 71; no water levels or operating rules |

**GFW concession and plantation polygons, checked 2026-10-16: not retrievable from here, and the Indonesian concessions are not openly licensed.**
- GFW's own Data API metadata (`data-api.globalforestwatch.org/datasets`) gives `gfw_oil_palm` and `gfw_wood_fiber` the licence "CC BY 4.0 (excluding Indonesia)" and `idn_wood_fiber` "View Only, Not Downloadable". So the Indonesian oil palm and wood fiber **concession** layers should not be used as open data.
- The openly licensed (CC BY 4.0) layer is the Spatial Database of Planted Trees (`gfw_planted_forests`, SDPT v2.0, Richter et al. 2024; versions up to `v20231128`) and the older "Tree plantations by type" (Transparent World). They give **plantation type** (oil palm, wood fiber, other), not concession boundaries.
- Access: the ArcGIS server `gis-gfw.wri.org` answers every query with HTTP 500 (all layers tested), the Open Data Hub export endpoints fail, the public S3 copy of the SDPT geodatabase returns 403, and the Data API query needs an API key (free, tied to a GFW account). Nothing was downloaded.
- To proceed: download the SDPT polygons for the KHG from the GFW or Global Nature Watch portal in a browser, or create a GFW Data API key, or use concession polygons you hold (BRGM, KLHK). Put them in `_data`, add them to `re-peat/sites/data_catalog.csv`, and attach them to sub-KHG by overlay.

What is **not** open: weir operating rules and water-level targets per concession. They sit with the concession holders
(the SiTMAT stations are their monitoring). Without them, neraca air can only describe the natural balance, not managed levels.

SIPALAGA (BRG, sipalaga.brg.go.id): a crawl of its daily PDF reports is in `C:/Users/danyl/Documents/Github/sipalaga-crawler` (outside this repo). The CSVs hold hourly groundwater level, soil moisture and **station rainfall** for BRG's own stations, but only **2019-02-19 to 2019-03-17** (about four wet-season weeks), with no coordinates (names only). Inside our two test KHG: SUNGAI_GAUNG_1/2 (Kampar-Gaung) and PADANG_SUGIHAN_1-3, PS1-SEBOKOR, LUMPUR1/2 (Sugihan-Lumpur). Use: a check of CHIRPS and ERA5 rain against gauges in that window; too short and too wet to calibrate neraca air. Not ingested yet. If the crawler runs again it could build a multi-year record.

Sentinel-1 result (retired bucket experiment `repeat_neraca.bucket.sentinel1`, report in `repeat-neraca/docs/bucket_reports/kampar_gaung_sentinel1.md`): within a station a brighter VV scene
falls on a shallower water table (median Spearman -0.38); across stations the VV-VH ratio ranks peak depth (0.53; out-of-fold RMSE 20.6 against 24.6 cm
for no skill) but not the share of days deeper than 40 cm. Per orbit the result is the same (0.52 for both tracks) and inside the tree class it is 0.48, so it is not geometry or WorldCover class. But concession (read from the SiTMAT station id) explains 64% of peak depth variance and carries much of the radar signal: inside concessions rho is 0.21; with whole concessions held out, RMSE 23 against 28 cm. Radar sees management differences between concessions more than differences inside them.

Suggested order of the remaining tests (each one a repo script scored with the same spatial cross-validation and verdict gate):
1. Concession polygons and water-level targets from the concession holders (GFW wood-fibre polygons are view-only, oil palm alone is incomplete).
2. MOD16 ET and CHIRPS in place of ERA5 E and P: does the out-of-fold RMSE beat the no-skill baseline (15.3 cm)?
3. Concession type as a covariate (was `repeat_neraca.bucket.covariates`, retired 2026-10-26).
