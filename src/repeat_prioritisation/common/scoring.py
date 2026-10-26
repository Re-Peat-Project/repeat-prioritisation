"""Turn per-unit indicators into urgency, impact, feasibility scores and priority classes."""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr

log = logging.getLogger("prioritas.scoring")

# group: u = urgency, i = impact, f = feasibility; direction +1 = higher value -> higher score
INDICATOR_DEFAULTS = {
    "u_deficit":        {"group": "u", "weight": 0.5, "direction": 1, "label": "Defisit air klimatik musim kemarau"},
    "u_wb_mean":        {"group": "u", "weight": 1.0, "direction": -1, "label": "Neraca air bulanan rerata"},
    "u_deficit_months": {"group": "u", "weight": 1.0, "direction": 1, "label": "Jumlah bulan defisit per tahun"},
    "u_deficit_elnino": {"group": "u", "weight": 0.5, "direction": 1, "label": "Defisit air tahun El Niño"},
    "u_ndmi":           {"group": "u", "weight": 1.0, "direction": -1, "label": "NDMI musim kemarau"},
    "u_dryspell":       {"group": "u", "weight": 0.5, "direction": 1, "label": "Hari kering berturut-turut"},
    "u_ndvi":           {"group": "u", "weight": 0.0, "direction": -1, "label": "NDVI musim kemarau"},
    "u_dry_days_mean":  {"group": "u", "weight": 0.0, "direction": 1, "label": "Rerata panjang periode kering"},
    "u_spell14":        {"group": "u", "weight": 0.5, "direction": 1, "label": "Jumlah periode kering >= 14 hari"},
    "u_fire_freq":      {"group": "u", "weight": 2.0, "direction": 1, "label": "Frekuensi terbakar"},
    "u_hotspot":        {"group": "u", "weight": 1.0, "direction": 1, "label": "Kepadatan titik api"},
    # from the national layers (national.profile; sub-KHG through subkhg.national_layers); weight 0 here, set per program
    "u_burn_repeat":    {"group": "u", "weight": 0.0, "direction": 1, "label": "Porsi terbakar dua kali atau lebih"},
    "u_hotspot_now":    {"group": "u", "weight": 0.0, "direction": 1, "label": "Kepadatan titik api tahun ini"},
    "u_canal_primary":  {"group": "u", "weight": 0.0, "direction": 1, "label": "Kerapatan kanal primer"},
    "u_canal_secondary": {"group": "u", "weight": 0.0, "direction": 1, "label": "Kerapatan kanal sekunder"},
    "u_canal_tertiary": {"group": "u", "weight": 0.0, "direction": 1, "label": "Kerapatan kanal tersier"},
    "u_canal_density":  {"group": "u", "weight": 1.0, "direction": 1, "label": "Kerapatan kanal"},
    "u_tma":            {"group": "u", "weight": 1.0, "direction": 1, "label": "Hari TMA > 0,4 m"},
    "u_tma_recession":  {"group": "u", "weight": 1.0, "direction": 1, "label": "Laju penurunan TMA hari kering"},
    "u_ipg_gap":        {"group": "u", "weight": 1.5, "direction": 1, "label": "Kekurangan sekat (1 - metrik IPG)"},
    "i_peat_depth":     {"group": "i", "weight": 2.0, "direction": 1, "label": "Kedalaman gambut"},
    "i_water_stock":    {"group": "i", "weight": 0.0, "direction": 1, "label": "Cadangan air gambut (m)"},
    "i_protected":      {"group": "i", "weight": 1.0, "direction": 1, "label": "Porsi fungsi lindung"},
    "i_exposure":       {"group": "i", "weight": 1.0, "direction": 1, "label": "Kedekatan permukiman"},
    "i_forest":         {"group": "i", "weight": 1.0, "direction": 1, "label": "Porsi hutan tersisa"},
    "f_reach":          {"group": "f", "weight": 2.0, "direction": 1, "label": "Porsi terjangkau kanal"},
    "f_water_dist":     {"group": "f", "weight": 1.0, "direction": -1, "label": "Jarak ke sumber air"},
    "f_lift":           {"group": "f", "weight": 1.0, "direction": -1, "label": "Beda tinggi dari sumber air"},
    "f_access":         {"group": "f", "weight": 0.5, "direction": -1, "label": "Jarak ke jalan"},
}

CLASS_ORDER = ["Prioritas 1: pembasahan", "Prioritas 2: pembasahan", "Siaga pemadaman",
               "Pantau dan rencanakan", "Pantau", "Pengaruh pasang surut: pantau",
               "Dikecualikan (pengelolaan lahan)"]
KHG_CLASSES = ["Fokus nasional: tinggi", "Fokus nasional: sedang", "Fokus nasional: rendah"]


def ahp_weights(matrix) -> tuple[np.ndarray, float]:
    """Principal-eigenvector weights and consistency ratio for a pairwise comparison matrix."""
    A = np.asarray(matrix, dtype=float)
    n = A.shape[0]
    vals, vecs = np.linalg.eig(A)
    k = int(np.argmax(vals.real))
    w = np.abs(vecs[:, k].real)
    w = w / w.sum()
    ci = (vals[k].real - n) / (n - 1) if n > 2 else 0.0
    ri = {1: 0, 2: 0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49}.get(n, 1.49)
    return w, (ci / ri if ri else 0.0)


def resolve_weights(cfg) -> tuple[dict, dict]:
    spec = {k: dict(v) for k, v in INDICATOR_DEFAULTS.items()}
    for k, v in (cfg.get("indicators") or {}).items():
        # a new indicator (e.g. from extra_indicators) defaults to group = its prefix, higher = more urgent
        spec.setdefault(k, {"group": k[0], "direction": 1, "weight": 1.0, "label": k}).update(v)
    ahp_info = {}
    for grp, a in (cfg.get("ahp") or {}).items():
        w, cr = ahp_weights(a["matrix"])
        for name, wi in zip(a["indicators"], w):
            spec[name]["weight"] = float(wi)
        ahp_info[grp] = {"weights": dict(zip(a["indicators"], map(float, w))), "consistency_ratio": float(cr)}
        if cr > 0.1:
            log.warning("AHP group %s: consistency ratio %.2f > 0.10, revise the pairwise matrix", grp, cr)
    spec = {k: v for k, v in spec.items() if v.get("enabled", True) and v.get("weight", 0) > 0}
    return spec, ahp_info


def normalise(df: pd.DataFrame, spec: dict, lo_q=0.05, hi_q=0.95, min_units=20) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for k, s in spec.items():
        if k not in df:
            continue
        if df[k].notna().sum() < min_units:
            if df[k].notna().any():
                log.warning("indicator %s available for only %d units (< %d); reported but not scored",
                            k, int(df[k].notna().sum()), min_units)
            continue
        x = df[k].astype(float)
        lo, hi = x.quantile(lo_q), x.quantile(hi_q)
        if not np.isfinite(lo) or hi - lo <= 1e-12:
            log.warning("indicator %s has no spread; skipped", k)
            continue
        z = ((x - lo) / (hi - lo)).clip(0, 1)
        out["n_" + k] = 1 - z if s["direction"] < 0 else z
    return out


def normalise_scoped(df, spec, sc):
    lo, hi = sc["normalise_quantiles"]
    mu = int(sc["min_units_per_indicator"])
    if sc.get("normalise_scope", "all") == "khg":
        parts = [normalise(g, spec, lo, hi, min(mu, max(3, len(g) // 2))) for _, g in df.groupby("khg_id")]
        return pd.concat(parts).reindex(df.index)
    return normalise(df, spec, lo, hi, min(mu, max(3, len(df) // 2)))


def group_score(norm: pd.DataFrame, spec: dict, grp: str, weights: dict | None = None):
    cols = [c for c in norm.columns if spec[c[2:]]["group"] == grp]
    if not cols:
        return pd.Series(np.nan, index=norm.index), pd.Series(0.0, index=norm.index)
    W = np.array([(weights or {}).get(c[2:], spec[c[2:]]["weight"]) for c in cols], dtype=float)
    X = norm[cols].to_numpy(dtype=float)
    M = np.isfinite(X)
    num = np.nansum(np.where(M, X * W, 0), axis=1)
    den = np.sum(np.where(M, W, 0), axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        score = np.where(den > 0, num / den, np.nan)
    return pd.Series(score, index=norm.index), pd.Series(den / W.sum(), index=norm.index)


def classify(risk: pd.Series, feas: pd.Series, q=(1 / 3, 2 / 3), fixed=None) -> pd.Series:
    rq = fixed["risk"] if fixed else [risk.quantile(q[0]), risk.quantile(q[1])]
    fq = fixed["feasibility"] if fixed else [feas.quantile(q[0]), feas.quantile(q[1])]
    rc = np.digitize(risk.fillna(-1), rq)          # 0 low, 1 medium, 2 high
    fc = np.digitize(feas.fillna(-1), fq)
    lab = np.empty(len(risk), dtype=object)
    for i, (r, f) in enumerate(zip(rc, fc)):
        if r == 2:
            lab[i] = CLASS_ORDER[0] if f >= 1 else CLASS_ORDER[2]
        elif r == 1:
            lab[i] = CLASS_ORDER[1] if f == 2 else CLASS_ORDER[3]
        else:
            lab[i] = CLASS_ORDER[4]
    return pd.Series(lab, index=risk.index), (rq, fq)


def correlation_report(norm: pd.DataFrame, sc: dict) -> dict:
    """Spearman matrix of normalised indicators and the pairs above correlation_warn (double counting)."""
    if norm.shape[1] < 2:
        return {}
    rho = norm.corr(method="spearman", min_periods=int(sc["min_units_per_indicator"]))
    pairs = [(a_[2:], b_[2:], float(rho.loc[a_, b_])) for i, a_ in enumerate(rho.columns)
             for b_ in rho.columns[i + 1:]
             if np.isfinite(rho.loc[a_, b_]) and abs(rho.loc[a_, b_]) >= sc["correlation_warn"]]
    for p in pairs:
        log.warning("indicators %s and %s strongly correlated (rho=%.2f): consider dropping one", *p)
    return {"correlated_pairs": [{"a": p[0], "b": p[1], "spearman": round(p[2], 3)} for p in pairs],
            "_corr": rho}


def score(df: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, dict]:
    sc = cfg["scoring"]
    spec, ahp_info = resolve_weights(cfg)
    norm = normalise_scoped(df, spec, sc)
    out = pd.concat([df, norm], axis=1)
    out["skor_urgensi"], out["cakupan_urgensi"] = group_score(norm, spec, "u")
    if "tidal_share" in out and sc.get("tidal_mode") == "downweight":
        out["skor_urgensi"] = out["skor_urgensi"] * (1 - float(sc["tidal_factor"]) * out["tidal_share"].fillna(0))
    out["skor_dampak"], out["cakupan_dampak"] = group_score(norm, spec, "i")
    out["skor_kelayakan"], out["cakupan_kelayakan"] = group_score(norm, spec, "f")
    a = float(sc["alpha_urgency"])
    out["skor_risiko"] = a * out["skor_urgensi"] + (1 - a) * out["skor_dampak"].fillna(out["skor_urgensi"])
    if sc.get("national") or out["skor_kelayakan"].notna().sum() == 0:
        q1, q2 = out["skor_risiko"].quantile([1 / 3, 2 / 3])
        out["kelas"] = np.where(out["skor_risiko"] >= q2, KHG_CLASSES[0],
                                np.where(out["skor_risiko"] >= q1, KHG_CLASSES[1], KHG_CLASSES[2]))
        thr = ([float(q1), float(q2)], [])
        order = {c: i for i, c in enumerate(KHG_CLASSES)}
    else:
        out["kelas"], thr = classify(out["skor_risiko"], out["skor_kelayakan"], fixed=sc.get("fixed_thresholds"))
        order = {c: i for i, c in enumerate(CLASS_ORDER)}
        if "tidal_share" in out and sc.get("tidal_mode") == "exclude":
            out.loc[out["tidal_share"].fillna(0) >= 0.5, "kelas"] = CLASS_ORDER[5]
        if "porsi_dikecualikan" in out:
            out.loc[out["porsi_dikecualikan"].fillna(0) >= 0.5, "kelas"] = CLASS_ORDER[6]
    out["urutan_kelas"] = out["kelas"].map(order)
    out = out.sort_values(["urutan_kelas", "skor_risiko"], ascending=[True, False])
    out["peringkat"] = np.arange(1, len(out) + 1)

    report = {"weights": {k: v["weight"] for k, v in spec.items()}, "ahp": ahp_info,
              "class_thresholds": {"risk": list(map(float, thr[0])), "feasibility": list(map(float, thr[1]))},
              "indicators_used": [c[2:] for c in norm.columns],
              "class_counts": out["kelas"].value_counts().to_dict()}

    # correlation check (double counting)
    report.update(correlation_report(norm, sc))

    # weight sensitivity
    if sc["sensitivity_runs"] > 0:
        out, sens = sensitivity(out, norm, spec, sc)
        report["sensitivity"] = sens

    # validation against held-out years
    report["validation"] = validate(out, sc)
    return out, report


def sensitivity(out, norm, spec, sc, high_fn=None, p_col="p_prioritas1"):
    """high_fn(risk, feasibility) -> boolean array: which units count as top class in a run (default: Prioritas 1)."""
    rng = np.random.default_rng(sc["seed"])
    R = int(sc["sensitivity_runs"])
    kappa = float(sc["sensitivity_concentration"])
    names = list(spec.keys())
    base = np.array([spec[n]["weight"] for n in names], dtype=float)
    top_q = float(sc["top_fraction"])
    hits_top = np.zeros(len(out))
    hits_p1 = np.zeros(len(out))
    ranks = []
    norm_o = norm.loc[out.index]
    for _ in range(R):
        w = {}
        for g in ("u", "i", "f"):
            idx = [i for i, n in enumerate(names) if spec[n]["group"] == g]
            if not idx:
                continue
            b = base[idx] / base[idx].sum()
            draw = rng.dirichlet(b * kappa + 1e-6)
            for i, d in zip(idx, draw):
                w[names[i]] = d
        a = float(np.clip(sc["alpha_urgency"] + rng.uniform(-0.1, 0.1), 0, 1))
        u, _ = group_score(norm_o, spec, "u", w)
        im, _ = group_score(norm_o, spec, "i", w)
        f, _ = group_score(norm_o, spec, "f", w)
        r = a * u + (1 - a) * im.fillna(u)
        hits_top += (r >= r.quantile(1 - top_q)).to_numpy()
        if high_fn is None:
            k, _ = classify(r, f)
            hits_p1 += (k == CLASS_ORDER[0]).to_numpy()
        else:
            hits_p1 += np.asarray(high_fn(r, f), dtype=float)
        ranks.append(rankdata(-r.fillna(-1)))
    out = out.copy()
    out["p_top_risiko"] = hits_top / R
    out[p_col] = hits_p1 / R
    out["sd_peringkat"] = np.std(np.stack(ranks), axis=0)
    stable = float(((out[p_col] >= 0.8) | (out[p_col] <= 0.2)).mean())
    return out, {"runs": R, "share_units_stable_class": stable,
                 "median_rank_sd": float(np.median(out["sd_peringkat"]))}


def _auc(score, label):
    ok = np.isfinite(score) & np.isfinite(label)
    s, y = score[ok], label[ok].astype(bool)
    npos, nneg = y.sum(), (~y).sum()
    if npos == 0 or nneg == 0:
        return None
    r = rankdata(s)
    return float((r[y].sum() - npos * (npos + 1) / 2) / (npos * nneg))


def _capture(score, target, area, q):
    ok = np.isfinite(score) & np.isfinite(target)
    s, t, a = score[ok], target[ok], area[ok]
    tot = np.sum(t * a)
    if tot <= 0:
        return None
    top = s >= np.quantile(s, 1 - q)
    return float(np.sum(t[top] * a[top]) / tot)


def validate(out: pd.DataFrame, sc) -> dict:
    res = {}
    q = float(sc["top_fraction"])
    area = out["area_km2"].to_numpy(dtype=float)
    candidates = {"skor_risiko": out["skor_risiko"], "skor_urgensi": out["skor_urgensi"]}
    if "u_fire_freq" in out:
        candidates["hanya_riwayat_kebakaran"] = out["u_fire_freq"]
    for tgt, thr in (("v_burned_frac", sc["validation_burn_threshold"]), ("v_hotspot", None)):
        if tgt not in out or out[tgt].notna().sum() < 10 or np.nanmax(out[tgt]) <= 0:
            continue
        t = out[tgt].to_numpy(dtype=float)
        lab = (t >= thr) if thr is not None else (t > 0)
        block = {"n_units": int(np.isfinite(t).sum()), "positive_units": int(np.nansum(lab))}
        for name, s in candidates.items():
            s = s.to_numpy(dtype=float)
            ok = np.isfinite(s) & np.isfinite(t)
            rho = spearmanr(s[ok], t[ok]).correlation if ok.sum() > 3 else None
            block[name] = {"auc": _auc(s, lab.astype(float)),
                           f"capture_top{int(q * 100)}pct": _capture(s, t, area, q),
                           "spearman": None if rho is None or not np.isfinite(rho) else float(rho)}
        block["random_capture_expected"] = q
        res[tgt] = block
        r = block["skor_risiko"]
        log.info("validation %s: AUC=%s, top %d%% units capture %s of target",
                 tgt, None if r["auc"] is None else round(r["auc"], 3), int(q * 100),
                 None if r[f"capture_top{int(q * 100)}pct"] is None else f"{r[f'capture_top{int(q*100)}pct']:.0%}")
    return res
