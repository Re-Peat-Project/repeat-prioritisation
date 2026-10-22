"""Checks for national.profile.rank that need no data: python -m tests.test_national_profile"""
import copy

import numpy as np
import pandas as pd

from national import profile as P


def _prof(n=90, seed=1):
    rng = np.random.default_rng(seed)
    fire = np.where(np.arange(n) < n // 3, 0.0, rng.gamma(2, 0.02, n))          # a third with no fire at all
    return pd.DataFrame({
        "khg_id": [f"K{i}" for i in range(n)], "area_km2": np.where(np.arange(n) % 10 == 0, 20.0, 500.0),
        "u_fire_freq": fire, "u_burn_repeat": fire / 2, "u_hotspot": fire * 20,
        "u_canal_density": np.where(np.arange(n) % 7 == 0, np.nan, rng.uniform(0, 5, n)),
        "v_burned_frac": fire, "v_hotspot": fire * 10, "geometry": [None] * n})


def test_rank():
    cfg = copy.deepcopy(P.DEFAULTS)
    cfg["scoring"]["sensitivity_runs"] = 20
    prof = _prof()
    out, rep = P.rank(prof, cfg, "validate")
    small = out[out.kelas == "Tidak diperingkat (KHG kecil)"]
    assert len(small) == (prof.area_km2 < cfg["min_area_km2"]).sum() and small.skor_risiko.isna().all()
    ranked = out[out.skor_risiko.notna()]
    assert set(ranked.kelas) <= {"Fokus nasional: tinggi", "Fokus nasional: sedang", "Fokus nasional: rendah"}
    assert (ranked.loc[ranked.skor_risiko <= 0, "kelas"] == "Fokus nasional: rendah").all()   # no fire signal is always Low
    top = ranked.sort_values("peringkat")
    assert top.kelas.iloc[0] == "Fokus nasional: tinggi" and top.skor_risiko.is_monotonic_decreasing
    assert ranked[ranked.u_canal_density.isna()].skor_risiko.notna().all()                       # missing canals are not scored, not zero
    assert rep["n_ranked"] == len(ranked) and "p_fokus_tinggi" in ranked
    out2, rep2 = P.rank(prof, cfg, "operational")
    assert rep2["validation"] == {} and out2.skor_risiko.notna().sum() == len(ranked)


def test_operational_extends_years(tmp_path=None):
    """main() must widen the baseline before the indicators are built (the first version only widened a copy in rank())."""
    import inspect
    src = inspect.getsource(P.main)
    assert 'a.mode == "operational"' in src and src.index('a.mode == "operational"') < src.index("build_profile(")


def test_current_year_term():
    """The current year is after the held-out years: out of --mode validate, in the operational score at its own weight."""
    cfg = copy.deepcopy(P.DEFAULTS)
    cfg["scoring"]["sensitivity_runs"] = 0
    prof = _prof()
    prof["u_hotspot_now"] = prof["u_hotspot"] * 0.5
    prof["hs_now_kept"] = prof["u_hotspot_now"] * 100
    _, rv = P.rank(prof, cfg, "validate")
    oo, ro = P.rank(prof, cfg, "operational")
    assert "u_hotspot_now" not in rv["weights"] and ro["weights"].get("u_hotspot_now") == 1.0
    assert {"peringkat_now", "peringkat_now_n"} <= set(oo.columns)
    top = oo[oo.skor_risiko.notna()].sort_values("peringkat_now")
    assert top["u_hotspot_now"].is_monotonic_decreasing                  # the standalone rank follows density


if __name__ == "__main__":
    test_rank()
    test_operational_extends_years()
    test_current_year_term()
    print("ok")
