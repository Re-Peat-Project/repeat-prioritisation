"""The stand-alone pages next to the dashboard: the KHG table (every KHG, every field) and the method page.

Both read the outputs of `repeat-national-final` (final/) and the dashboard's data cache (dashboard_data.json, for the
per-KHG time series and the data confidence). Built by `repeat-national-dashboard`; nothing here computes a score.
"""
import json
from pathlib import Path

import pandas as pd

ASSETS = Path(__file__).with_name("assets")

# the columns of final_khg.csv the table shows besides the indicators of the rule (read from final_meta.json)
EXTRA = ["n_desa_target", "n_dmpg", "n_tma_stations", "priority_ha", "c_holders", "c_contested", "depth_known_share", "lc_known_share", "u_burned_now"]


def _nz(s, nd=4):
    return [None if pd.isna(x) else round(float(x), nd) for x in s]


def table_payload(out, data, profiles):
    fd = Path(out) / "final"
    f = pd.read_csv(fd / "final_khg.csv")
    meta = json.loads((fd / "final_meta.json").read_text(encoding="utf-8"))
    rule = meta["rule"]
    K = data["khg"]
    ki = {k: i for i, k in enumerate(K["id"])}
    inds = [k for spec in rule["dimensions"].values() for k in spec] + [k for k in rule.get("reported", []) if k in f] + [k for k in EXTRA if k in f]
    inds = list(dict.fromkeys(inds))
    flag = lambda c: [int(bool(x)) if not pd.isna(x) else 0 for x in f[c]] if c in f else [0] * len(f)

    def series(kid, key, years, col=1):
        p = profiles.get(kid) or {}
        d = {int(r[0]): r[col] for r in p.get(key) or []}
        return [None if d.get(y) is None else round(float(d[y]), 3) for y in years]
    yb, yh = list(range(2015, 2027)), list(range(2012, 2027))
    rows = {
        "id": f.khg_code.tolist(),
        "name": f.khg_name.str.replace(r"^KHG\s+", "", regex=True).str.replace(r"\s+", " ", regex=True).tolist(),
        "prov": f.provinces.fillna("").tolist(), "isl": f.island.fillna("").tolist(),
        "k337": flag("klh_337"), "k362": flag("klh_priority_362"), "team": [K["team"][ki[k]] if k in ki else "" for k in f.khg_code],
        "tim": f.klh_337_team.fillna("").astype(str).tolist() if "klh_337_team" in f else [""] * len(f),
        "type": [x if isinstance(x, str) else None for x in f["type"]], "iv": [x if isinstance(x, str) else None for x in f.get("intervention", [None] * len(f))],
        "ru": [None if pd.isna(x) else int(x) for x in f.rank_urgency], "ru337": [None if pd.isna(x) else int(x) for x in f.rank_urgency_337],
        "rt": [None if pd.isna(x) else int(x) for x in f.rank_in_type],
        "pool": flag("in_pool"), "wk": flag("whole_khg"), "lowf": flag("flag_low_feasibility"), "hix": flag("flag_high_exposure"),
        "area": [K["area"][ki[k]] if k in ki else None for k in f.khg_code], "conf": [K["conf"][ki[k]] if k in ki else None for k in f.khg_code],
        "dims": {d: _nz(f[d]) for d in ["urgency", "stake", "complexity", "feasibility", "people"] if d in f},
        "ind": {k: _nz(f[k], 6) for k in inds},
        "burned": [series(k, "burned", yb) for k in f.khg_code], "hs": [series(k, "hs", yh) for k in f.khg_code],
        "now_m": [[(dict((int(m[0]), m[1]) for m in (profiles.get(k) or {}).get("now_m") or []).get(i)) for i in range(1, 13)] for k in f.khg_code],
    }
    return {"rows": rows, "years": {"burned": yb, "hs": yh},
            "meta": {"dims": {d: {k: v["weight"] for k, v in spec.items()} for d, spec in rule["dimensions"].items()},
                     "dirs": {k: v.get("direction", "+") for spec in rule["dimensions"].values() for k, v in spec.items()},
                     "reported": [k for k in rule.get("reported", []) if k in f], "extra": [k for k in EXTRA if k in f],
                     "min_peat": rule.get("min_peat_km2"), "intervention": rule.get("intervention"), "run": meta.get("run"),
                     "generated": data["meta"].get("generated"), "period_now": data["meta"].get("period_now")}}


def method_payload(out, data):
    K = data["khg"]
    fd = Path(out) / "final"
    f = pd.read_csv(fd / "final_khg.csv")
    meta = json.loads((fd / "final_meta.json").read_text(encoding="utf-8"))
    rule = meta["rule"]
    types = pd.read_csv(fd / "final_types.csv")
    iv = f[f.type.notna()].groupby("intervention").agg(khg=("khg_code", "size"), in_337=("klh_337", "sum")).reset_index()
    ivt = pd.crosstab(f.loc[f.klh_337.astype(bool) & f.type.notna(), "type"], f.loc[f.klh_337.astype(bool) & f.type.notna(), "intervention"])
    return {"rule": {"written": rule.get("written"), "version": rule.get("version"), "min_peat": rule.get("min_peat_km2"),
                     "dims": {d: {k: v["weight"] for k, v in spec.items()} for d, spec in rule["dimensions"].items()},
                     "dirs": {k: v.get("direction", "+") for spec in rule["dimensions"].values() for k, v in spec.items()},
                     "reported": rule.get("reported", []), "intervention": rule.get("intervention"), "buffer_km": rule.get("inputs_layers", {}).get("exposure_buffer_km")},
            "cuts": meta["tercile_cuts"], "fcut": meta.get("feasibility_low_cut"), "pcut": meta.get("people_high_cut"),
            "n": {"khg": int(len(f)), "k337": int(f.klh_337.sum()), "scored": int(f.type.notna().sum()), "pool": int(f.in_pool.fillna(False).astype(bool).sum()),
                  "scored337": int((f.klh_337.astype(bool) & f.type.notna()).sum()), "whole": int(f.get("whole_khg", pd.Series(False)).fillna(False).astype(bool).sum()),
                  "team": int(sum(1 for x in K["team"] if x)), "peat_km2": round(float(f.loc[~f.get("whole_khg", pd.Series(False, index=f.index)).fillna(False).astype(bool), "peat_km2"].sum()), 0)},
            "types": types.to_dict("records"), "iv": iv.to_dict("records"),   # peat_km2 above: KLH peat only (whole-KHG stand-ins excluded)
            "ivt": {ty: {k: int(v) for k, v in r.items()} for ty, r in ivt.iterrows()},
            "run": meta.get("run"), "generated": data["meta"].get("generated"), "period_now": data["meta"].get("period_now")}


def _page(tpl, js, payload, out_path):
    common = (ASSETS / "page.js").read_text(encoding="utf-8").replace("/*I18N*/", (ASSETS / "i18n_id.js").read_text(encoding="utf-8"))
    script = common + "\n" + (ASSETS / "defs.js").read_text(encoding="utf-8") + "\n" + (ASSETS / js).read_text(encoding="utf-8")
    html = ((ASSETS / tpl).read_text(encoding="utf-8")
            .replace("/*D3*/", (ASSETS / "d3.v7.9.0.min.js").read_text(encoding="utf-8"))
            .replace("/*CSS*/", (ASSETS / "dashboard.css").read_text(encoding="utf-8"))
            .replace("/*DATA*/", "const DATA=" + json.dumps(payload, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/") + ";")
            .replace("/*JS*/", "(function(){\n\"use strict\";\n" + script + "\n})();"))
    Path(out_path).write_text(html, encoding="utf-8")
    print(f"{out_path}: {len(html) / 1e6:.1f} MB")


def build(out, data, profiles, out_dir):
    if not (Path(out) / "final" / "final_khg.csv").exists():
        return
    _page("khg_table.html", "table.js", table_payload(out, data, profiles), Path(out_dir) / "khg_table.html")
    _page("method.html", "method.js", method_payload(out, data), Path(out_dir) / "method.html")
