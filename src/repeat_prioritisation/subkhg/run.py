#!/usr/bin/env python3
"""Sub-KHG prioritisation: the sub-KHG polygons of repeat-delineation (or hexagons / your polygons) inside each KHG,
full indicator set at 30 m, ranked by need for intervention, canal-block needs.

  python -m subkhg.run --config configs/local/subkhg.yaml
  python -m subkhg.run --config configs/local/subkhg.yaml --skip-fetch     # re-score from cache
  python -m subkhg.run --print-default-config > configs/local/subkhg.yaml
"""
from common import pipeline
from subkhg.prioritise import CLASS_COLORS, score_need
from subkhg.priority_export import EXPORT_DEFAULTS, write_priority

PRESET = {
    "units": {"mode": "vector"},      # path: subkhg_units.gpkg from repeat-delineation
    "grid_res_m": 30,
    "years": {"baseline": [2015, 2022]},     # 2015 included: Permen LHK 7/2022 counts land burnt since 2015
    "scoring": {"alpha_urgency": 0.8, "normalise_scope": "khg"},
    "priority_export": EXPORT_DEFAULTS,         # subkhg_priority.csv for repeat-pump: neraca_khg path and design_period_days
    # The rainfall indicators have weight 0 in the need ranking (see prioritise.py), so skip the slow ERA5 reads
    # (about 4 min per KHG-year, 20 more per year TerraClimate lacks). Set sources.era5.enabled: true to fetch them.
    "sources": {"era5": {"enabled": False}},
}

if __name__ == "__main__":
    pipeline.main("subkhg", PRESET, __doc__, score=score_need, class_colors=CLASS_COLORS, after=write_priority)
