#!/usr/bin/env python3
"""National KHG prioritisation: one unit per KHG, coarse wall-to-wall layers (250 m grid).

  python -m national.run --config configs/local/national.yaml
  python -m national.run --print-default-config > configs/local/national.yaml
"""
from common import pipeline

PRESET = {
    "units": {"mode": "khg"},
    "grid_res_m": 250,
    "sources": {"ndmi": {"enabled": False}},
    # indicators that need canal reach, DTM or fine layers are only meaningful per sub-KHG
    "indicators": {"f_reach": {"weight": 0}, "f_lift": {"weight": 0}, "f_access": {"weight": 0},
                   "u_ipg_gap": {"weight": 0}, "f_water_dist": {"weight": 0}},
    "scoring": {"national": True, "sensitivity_runs": 0, "normalise_scope": "all"},
}

if __name__ == "__main__":
    pipeline.main("khg", PRESET, __doc__)
