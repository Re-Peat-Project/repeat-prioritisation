"""Checks for national.profile.rank that need no data: python -m tests.test_national_profile"""
import copy

import numpy as np
import pandas as pd

from repeat_prioritisation.national import profile as P


def _prof(n=90, seed=1):
    rng = np.random.default_rng(seed)
    fire = np.where(np.arange(n) < n // 3, 0.0, rng.gamma(2, 0.02, n))          # a third with no fire at all
    return pd.DataFrame({
        "khg_id": [f"K{i}" for i in range(n)], "area_km2": np.where(np.arange(n) % 10 == 0, 20.0, 500.0),
        "u_fire_freq": fire, "u_burn_repeat": fire / 2, "u_hotspot": fire * 20,
        "u_canal_density": np.where(np.arange(n) % 7 == 0, np.nan, rng.uniform(0, 5, n)),
        "u_canal_primary": np.where(np.arange(n) % 7 == 0, np.nan, rng.uniform(0, 1, n)),
        "u_canal_secondary": np.where(np.arange(n) % 7 == 0, np.nan, rng.uniform(0, 2, n)),
        "u_canal_tertiary": np.where(np.arange(n) % 7 == 0, np.nan, rng.uniform(0, 3, n)),
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
    assert ranked[ranked.u_canal_primary.isna()].skor_risiko.notna().all()                       # missing canals are not scored, not zero
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


def _units_and_points(tmp):
    """Two units and hotspot files whose points all fall outside them (a KHG with no detection)."""
    import geopandas as gpd
    from shapely.geometry import Point, box
    units = gpd.GeoDataFrame({"khg_id": ["U1", "U2"]}, geometry=[box(100, 0, 100.1, 0.1), box(100.1, 0, 100.2, 0.1)], crs=4326)
    far = [Point(110, -2), Point(110.01, -2)]
    viirs = gpd.GeoDataFrame({"year": [2019, 2020], "confidence": ["n", "h"], "type": [0, 0], "frp": [5.0, 7.0]},
                             geometry=far, crs=4326)
    now = gpd.GeoDataFrame({"month": [3, 7], "level": ["medium", "high"], "frp": [np.nan, 4.0],
                            "acq_date": ["2026-03-02", "2026-07-15"]}, geometry=far, crs=4326)
    viirs.to_file(f"{tmp}/viirs.gpkg")
    now.to_file(f"{tmp}/now.gpkg", layer="hotspots")
    return units


def test_hotspots_none_inside():
    """No detection in any unit: an empty table with the usual columns (not an error), and the profile's own
    reindex/fillna then gives every unit 0."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        units = _units_and_points(tmp)
        hs = P.hotspots_by_year(f"{tmp}/viirs.gpkg", units, {"types": [0], "confidence": ["n", "h"]})
        now, meta = P.hotspots_now(f"{tmp}/now.gpkg", units, {"levels": ["medium", "high"]})
    assert hs.empty and {"khg_id", "year", *P.HS_YEAR_COLS} <= set(hs.columns)
    assert now.empty and {"khg_id", "month", *P.HS_NOW_COLS} <= set(now.columns)
    assert meta["n_points"] == 2 and meta["n_inside"] == 0 and meta["last_date"] == "2026-07-15"
    hy = hs.pivot(index="khg_id", columns="year", values="n_hotspot").reindex(units.khg_id).fillna(0)
    assert (hy.sum(axis=1) == 0).all()                                    # as build_profile computes u_hotspot
    tot = now.groupby("khg_id")[P.HS_NOW_COLS].sum().reindex(units.khg_id).fillna(0)
    assert (tot["n_kept"] == 0).all() and len(tot) == 2                   # as build_profile computes u_hotspot_now


if __name__ == "__main__":
    test_rank()
    test_operational_extends_years()
    test_current_year_term()
    test_hotspots_none_inside()
    print("ok")
