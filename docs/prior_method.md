# Earlier prioritisation method

From the team's slide "Contoh Parameter Penentuan Prioritas Pembasahan dalam 1 KHG" (shared 2026-10-16). It ranks the sub-KHG of one KHG. This page transcribes it, compares it with the current sub-KHG program, and lists what follows.

## The method as the slide states it

| # | Indicator | Meaning | Direction as written |
|---|---|---|---|
| 1 | NDMI rerata | Land wetness | higher NDMI, smaller rank number |
| 2 | NDVI rerata | Vegetation greenness | higher NDVI, smaller |
| 3 | Kedalaman gambut rerata | Mean peat depth per sub-KHG | thicker peat, smaller |
| 3 (sic, probably 4) | Penurunan air | % loss or decline of water storage | smaller decline, smaller |
| 5 | Nilai neraca air | Mean daily water balance | higher balance, smaller |
| 6 | Frekuensi defisit air | Mean months in water deficit per year | rarer deficit, smaller |
| 7 | Rerata dry days | Mean consecutive days without rain | shorter, smaller |
| 8 | Riwayat kebakaran | Number of hotspots | fewer, smaller |

- Each indicator ranks the sub-KHG. **Total score = sum of (rank x weight)**, with equal weights (the slide: "Bobot 8 indikator = 1 (setara)").
- Example with 16 sub-KHG: sub-KHG 9 scores 26 and is rank 1; sub-KHG 16 scores 102 and is rank 16. A score of 102 from 8 indicators means weights of 1 each (8 x 1 gives 8 to 128), not weights that sum to 1.

**The logical meaning, used in the code:** for choosing where to intervene, rank 1 is the highest priority, so each indicator ranks the worst condition first (lowest NDMI, most hotspots, and so on) and thicker peat first. That matches the slide for peat depth and is the reverse of how the slide words the other seven. This is implemented as an option, see [../subkhg/README.md](../subkhg/README.md).

**Still to confirm with the team:** "smaller rank number" means the better condition (wetter, greener, less burnt). Read that way, rank 1 is the sub-KHG in the best condition, and rewetting priority is at the other end (highest total score). But then thicker peat gets a smaller number, which would make thick peat lower priority, the opposite of what one expects for carbon. Either the final rank 1 is meant as top priority and the other seven directions are inverted, or thin peat is treated as the degraded condition. The slide does not settle it.

## Compared with the current sub-KHG program

| Slide | Current program | Gap |
|---|---|---|
| 1 NDMI mean | `u_ndmi`: median of the Aug-Oct Sentinel-2 composite | Same idea (median, not mean). |
| 2 NDVI mean | none | Missing. Easy to add from the same Sentinel-2 scenes (B8, B4), or MODIS 13Q1 on Planetary Computer. |
| 3 Peat depth | `i_peat_depth` (needs the peat depth raster) | Present, but in the stakes group and "thicker = higher". Direction to confirm (above). |
| 4 Water decline % | none | Missing. A storage change over the dry season: it belongs to the neraca air module. |
| 5 Neraca air, daily mean | planned module; `u_wb_mean` is a monthly TerraClimate stand-in, now off | Missing at sub-KHG scale. |
| 6 Deficit months per year | `u_deficit_months` | Present, but 4-25 km data, so constant inside a KHG; off in the ranking. |
| 7 Mean dry days | `u_dryspell` is the **longest** dry run; `u_spell14` counts spells of 14 days or more | Different statistic. Mean run length is not computed. |
| 8 Hotspot count | `u_hotspot` (per km2 per year) and `u_fire_freq` (burned share) | Present, and richer. |

How the scores are combined also differs:

- **Ranks versus values.** The slide sums ranks, so only the order of sub-KHG matters. The program rescales each indicator to 0-1 (5th to 95th percentile) and takes a weighted mean, so differences in size count.
- **Equal weights versus ours.** The program's defaults weight fire history and peat depth at 2, others at 1 or 0.5. They are my choices, not agreed.
- **One sum versus need, stakes and feasibility.** The slide has a single total. The program ranks by need and reports feasibility for choosing the measure.

## What follows

1. **Rank sums amplify noise in near-constant indicators.** Indicators 5, 6 and 7 (and probably 4) come from rainfall and evaporation. If they are computed from products of 4-25 km, they are almost the same for every sub-KHG of a KHG. Ranking tiny differences gives each of them the same weight as NDMI. The smoke test showed what such differences are made of: `u_wb_mean` varied only through forest interception, and `u_dryspell` only through interpolation between a few cells. The slide's method needs rainfall and water balance at sub-KHG resolution, or those indicators drop out. Not tested here.
2. **The slide tells us what the neraca air module must output.** Indicators 4 to 7: mean daily water balance, % storage decline, months in deficit per year, mean dry days. The neraca air module now writes `u_wb_mean` and `u_deficit_months` per sub-KHG (`repeat-neraca`, `python -m repeat_neraca.balance`).
3. **The comparison is possible now.** The rank-sum is an option (`scoring.method: ranksum`) and both rankings are always written side by side, with their agreement in `laporan.json`.
4. **Indicators added for it:** NDVI (`u_ndvi`) and the mean dry-run length (`u_dry_days_mean`). The storage decline and the daily water balance wait for the neraca air module.
