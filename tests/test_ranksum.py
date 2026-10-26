"""Checks of the rank-sum method (subkhg/prioritise.py) against numbers worked out by hand.

    python -m tests.test_ranksum
"""
import numpy as np
import pandas as pd

from repeat_prioritisation.common import pipeline
from repeat_prioritisation.subkhg.prioritise import ranksum, score_need
from repeat_prioritisation.subkhg.run import PRESET


def _six():
    return pd.DataFrame({"khg_id": "A", "unit_id": list("abcdef"), "area_km2": 10.0,
                         "u_ndmi": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6],        # lowest NDMI = most need -> ranks 1..6
                         "u_hotspot": [6, 5, 4, 3, 2, 1],                 # most hotspots = most need -> ranks 1..6
                         "i_peat_depth": [10, 20, 30, 40, 50, 60]})       # thickest peat = rank 1 -> ranks 6..1


def test_hand_checked_totals():
    rs, info = ranksum(_six(), {"normalise_scope": "all"})
    assert info["used"] == ["u_ndmi", "i_peat_depth", "u_hotspot"]
    assert np.allclose(rs["skor_ranksum"], [8, 9, 10, 11, 12, 13])       # (1+1+6), (2+2+5), ...
    assert abs(rs["skor_ranksum_rel"].iloc[0] - 1 / 3) < 1e-9            # rel ranks (0, 0, 1) -> mean 1/3
    assert np.allclose(rs["cakupan_ranksum"], 3 / 8)                     # 3 of the 8 slide indicators exist


def test_ties_share_the_average_rank_and_missing_values_are_scaled_up():
    d = _six()
    d.loc[3, "u_hotspot"] = np.nan
    d["u_ndmi"] = [0.1, 0.1, 0.3, 0.4, 0.5, 0.6]
    rs, _ = ranksum(d, {"normalise_scope": "all"})
    assert rs["rk_u_ndmi"].iloc[:2].tolist() == [1.5, 1.5]
    assert abs(rs.loc[3, "skor_ranksum"] - (4 + 3) * 3 / 2) < 1e-9       # two of three indicators, scaled to the full weight


def test_ranks_restart_in_each_khg():
    d = pd.concat([_six(), _six().iloc[:4].assign(khg_id="B", unit_id=list("wxyz"))], ignore_index=True)
    rs, _ = ranksum(d, {"normalise_scope": "khg"})
    assert rs["rk_u_ndmi"].iloc[:6].tolist() == [1, 2, 3, 4, 5, 6]
    assert rs["rk_u_ndmi"].iloc[6:].tolist() == [1, 2, 3, 4]
    assert rs["skor_ranksum_rel"].iloc[0] == rs["skor_ranksum_rel"].iloc[6]    # comparable across KHG of different size


def test_weights_directions_and_column_alias():
    d = _six().assign(u_deficit_months_dry=[1, 2, 3, 4, 5, 5])
    rs, info = ranksum(d, {"normalise_scope": "all", "ranksum_weights": {"u_ndmi": 0, "u_hotspot": 3},
                           "ranksum_columns": {"u_deficit_months": "u_deficit_months_dry"}, "ranksum_directions": {"i_peat_depth": -1}})
    assert "u_ndmi" not in info["used"] and info["weights"]["u_hotspot"] == 3
    assert "u_deficit_months" in info["used"]                             # read from the alias column
    assert rs["rk_i_peat_depth"].tolist() == [1, 2, 3, 4, 5, 6]          # direction flipped: thinnest first


def test_methods_and_errors():
    rng = np.random.default_rng(3)
    n = 40
    big = pd.DataFrame({"khg_id": ["A"] * 25 + ["B"] * 15, "unit_id": [f"U{i}" for i in range(n)], "area_km2": 10.0})
    for c in ["u_ndmi", "u_ndvi", "i_peat_depth", "u_hotspot", "u_deficit_months", "u_dry_days_mean", "f_reach", "f_water_dist", "i_forest", "u_fire_freq"]:
        big[c] = rng.random(n)
    big["tidal_share"] = 0.0
    big["porsi_dikecualikan"] = 0.0
    cfg = pipeline.load_config(None, PRESET, "subkhg")
    for m in ("need", "ranksum"):
        cfg["scoring"]["method"] = m
        o, r = score_need(big.copy(), cfg)
        assert {"peringkat_need", "peringkat_ranksum", "skor_ranksum", "rk_u_ndmi"} <= set(o.columns)
        assert sorted(o["peringkat"]) == list(range(1, n + 1))
        assert ("sensitivity" in r) == (m == "need")                      # sensitivity runs belong to the need score only
    cfg["scoring"]["method"] = "bogus"
    try:
        score_need(big.copy(), cfg)
        raise AssertionError("an unknown method was accepted")
    except ValueError:
        pass
    cfg["scoring"]["method"] = "ranksum"
    try:
        score_need(big[["khg_id", "unit_id", "area_km2", "f_reach"]].copy(), cfg)
        raise AssertionError("ranksum ran without any of its indicators")
    except ValueError:
        pass


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
