#!/usr/bin/env python3
"""Map layers behind the prioritisation, for the profile map of the dashboard (and the same layers as the annex maps).

  repeat-national-extra-layers --config configs/examples/national_profile.yaml [--khg KHG.16.02.01 ...] [--workers 3]

Per KHG, clipped to it, each feature tagged k = khg_id:
  x_depth   peat thickness class (KLHK FEG via KLH's PPEG analysis), c = 0 (< 1 m) .. 4 (>= 5 m), 9 = no class
  x_dome    peat dome landform (BBSDLP via PPEG)
  x_skeg    SKEG 2024 damage, c = 0 (not damaged) .. 4 (very heavy)
  x_czone   canal-influence zone (PPEG KET_KANAL), c = p | s | t
  x_lc      land cover 2022 (PPEG PL_2022), c = forest | open | plantation | farm | settlement | water
  x_sf      social forestry: c = hd (village forest), htr (community plantation), iphps (IPHPS)
  x_pptpkh  PPTPKH (land being settled inside the forest estate)
  x_river, x_lake, x_road   RBI large rivers (two banks), lakes and reservoirs, roads (footpaths excluded)
  x_brgm    BRGM hydrological structures (points)
The polygon layers are dissolved per class (the PPEG layer is a coverage) and thinned to about 5 m, for display only.
Writes <out>/tiles/src/x_*.geojsonl (merged with the dashboard's own tile sources by repeat-national-tiles), and the people per
km2 (IHME Populace, `final.inputs_layers.population`) of each KHG as <out>/khg_tiles/pop/<khg_id>.png in Web Mercator, with
<out>/khg_tiles/pop/index.json (the corners of each image and the colour classes).
"""
from __future__ import annotations

import argparse
import copy
import json
import re
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pyogrio
import shapely
import yaml

from repeat_prioritisation.national import profile as P

PPEG = "ALL_Analysis_Integrasi_Tematik__PPEG_Indonesia__April_2026.gpkg"
OPEN = {"Semak Belukar Rawa", "Semak Belukar", "Lahan Terbuka", "Rawa", "Savana/ Padang Rumput", "Savana/Padang Rumput"}
SKEG = {"Tidak Rusak": 0, "Rusak Ringan": 1, "Rusak Sedang": 2, "Rusak Berat": 3, "Rusak Sangat Berat": 4}
ZONE = {"Kanal Primer": "p", "Kanal Sekunder": "s", "Kanal Tersier": "t"}
SMOOTH = 0.00005
POP_CLASSES = [1, 10, 100, 1000, 5000]      # people per km2, lower bounds of the colour classes
POP_COLORS = ["#fde9c9", "#f8c48a", "#ee8f50", "#cf5427", "#8c2a0e"]


def lc_class(s):
    s = s or ""
    if s.startswith("Hutan") and s != "Hutan Tanaman":
        return "forest"
    if s in OPEN:
        return "open"
    if s in ("Perkebunan", "Hutan Tanaman"):
        return "plantation"
    if s.startswith("Pertanian") or s == "Sawah":
        return "farm"
    if s == "Permukiman":
        return "settlement"
    if s == "Tubuh Air":
        return "water"
    return None


def depth_class(s):
    if not isinstance(s, str) or not s.strip() or "NON" in s:
        return 9
    m = re.search(r"(\d+(?:[.,]\d+)?)", s)
    if not m:
        return 9
    v = float(m.group(1).replace(",", "."))
    v = v / 100 if "cm" in s else v
    return 0 if v < 1 else 1 if v < 2 else 2 if v < 3 else 3 if v < 5 else 4


def feat(geom, **props):
    geom = shapely.set_precision(geom, 1e-5, mode="pointwise")
    if geom is None or geom.is_empty:
        return None
    return {"type": "Feature", "properties": props, "geometry": shapely.geometry.mapping(geom)}


def dissolve(geoms):
    geoms = [g for g in geoms if g is not None and not g.is_empty]
    if not geoms:
        return None
    try:
        u = shapely.coverage_union_all(shapely.make_valid(np.array(geoms)))
    except Exception:
        u = shapely.union_all(shapely.make_valid(np.array(geoms)))
    return u.simplify(SMOOTH, preserve_topology=True)


def polys_only(g):
    if g is None or g.is_empty:
        return None
    if g.geom_type in ("Polygon", "MultiPolygon"):
        return g
    parts = [p for p in getattr(g, "geoms", []) if p.geom_type in ("Polygon", "MultiPolygon")]
    return shapely.union_all(parts) if parts else None


def khg_features(cfg, kid, g):
    data = Path(cfg["data"])
    lay = cfg.get("final", {}).get("inputs_layers", {})
    bbox = g.bounds
    out = {}
    add = lambda layer, f: f and out.setdefault(layer, []).append(f)
    rd = lambda p, cols=None, where=None: pyogrio.read_dataframe(data / p, bbox=bbox, columns=cols, where=where) if (data / p).exists() else None
    pp = rd(PPEG, ["LAHAN_GAMB", "PEAT_THICK", "LANDFORM", "SKEG_2024", "KET_KANAL", "PL_2022"])
    if pp is not None and len(pp):
        rp = shapely.get_coordinates(pp.geometry.representative_point())
        pp = pp[shapely.contains_xy(g, rp[:, 0], rp[:, 1])]
        geo = shapely.intersection(shapely.make_valid(pp.geometry.values), g)
        peat = (pp.LAHAN_GAMB == "LAHAN GAMBUT").to_numpy()
        groups = {
            "x_depth": (peat, pp.PEAT_THICK.map(depth_class).to_numpy()),
            "x_skeg": (peat, pp.SKEG_2024.map(SKEG).to_numpy()),
            "x_czone": (np.ones(len(pp), bool), pp.KET_KANAL.map(ZONE).to_numpy()),
            "x_lc": (np.ones(len(pp), bool), pp.PL_2022.map(lc_class).to_numpy()),
        }
        for layer, (sel, cls) in groups.items():
            for c in [x for x in pd_unique(cls[sel]) if x is not None and not (isinstance(x, float) and np.isnan(x))]:
                u = polys_only(dissolve(geo[sel & (cls == c)]))
                add(layer, feat(u, k=kid, c=int(c) if isinstance(c, (int, np.integer, float)) else c) if u is not None else None)
        dome = peat & pp.LANDFORM.fillna("").str.contains("kubah", case=False).to_numpy()
        if dome.any():
            add("x_dome", feat(polys_only(dissolve(geo[dome])), k=kid))
    for c, p in (("hd", "tenure/hutan_desa.gpkg"), ("htr", "tenure/htr.gpkg"), ("iphps", "tenure/iphps.gpkg")):
        s = rd(p, [])
        if s is not None and len(s):
            u = polys_only(dissolve(shapely.intersection(shapely.make_valid(s.geometry.values), g)))
            add("x_sf", feat(u, k=kid, c=c) if u is not None else None)
    s = rd("tenure/pptpkh.gpkg", [])
    if s is not None and len(s):
        u = polys_only(dissolve(shapely.intersection(shapely.make_valid(s.geometry.values), g)))
        add("x_pptpkh", feat(u, k=kid) if u is not None else None)
    for layer, p, cols, keep in (("x_river", lay.get("rivers", "RBI_sungai.gpkg"), [], None), ("x_road", lay.get("roads", "Transportasi_Jalan_Detil.gpkg"), ["NAMA_UNSUR"],
                                  set(lay.get("road_classes", ["Jalan Tol", "Jalan Arteri", "Jalan Kolektor", "Jalan Lokal", "Jalan Lain"])))):
        s = rd(p, cols)
        if s is not None and len(s):
            if keep:
                s = s[s.NAMA_UNSUR.isin(keep)]
            for x in shapely.intersection(shapely.make_valid(s.geometry.values), g):
                if x is not None and not x.is_empty and x.geom_type in ("LineString", "MultiLineString"):
                    add(layer, feat(x.simplify(SMOOTH), k=kid))
    s = rd(lay.get("lakes", "RBI_wadukdanau.gpkg"), [])
    if s is not None and len(s):
        u = polys_only(dissolve(shapely.intersection(shapely.make_valid(s.geometry.values), g)))
        add("x_lake", feat(u, k=kid) if u is not None else None)
    s = rd(cfg["inputs"].get("blocks", "infrastruktur_hidrologis_existing_BRGM_Indonesia.gpkg"), ["Jenis"])
    if s is not None and len(s):
        xy = shapely.get_coordinates(s.geometry.values)
        if len(xy) == len(s):
            ins = shapely.contains_xy(g, xy[:, 0], xy[:, 1])
            for (x, y), j in zip(xy[ins], s.Jenis.fillna("").to_numpy()[ins]):
                add("x_brgm", feat(shapely.Point(x, y), k=kid, j=str(j)[:40]))
    return out


def pd_unique(a):
    seen, out = set(), []
    for x in a:
        key = x if not (isinstance(x, float) and np.isnan(x)) else "nan"
        if key not in seen:
            seen.add(key); out.append(x)
    return out


def pop_png(cfg, kid, g, outdir, max_px=1100):
    """People per km2 of one KHG on a Web Mercator grid (average of the 40 m cells), as a transparent PNG clipped to the KHG."""
    import rasterio
    from rasterio.features import geometry_mask
    from rasterio.warp import Resampling, reproject, transform_bounds, transform_geom
    from PIL import Image
    src_p = Path(cfg["data"]) / cfg.get("final", {}).get("inputs_layers", {}).get("population", "")
    if not src_p.is_file():
        return None
    with rasterio.open(src_p) as src:
        b = transform_bounds("EPSG:4326", src.crs, *g.bounds, densify_pts=21)
        win = rasterio.windows.from_bounds(*b, transform=src.transform).round_offsets().round_lengths()
        win = win.intersection(rasterio.windows.Window(0, 0, src.width, src.height))
        a = src.read(1, window=win, masked=False).astype("float32")
        a[~np.isfinite(a) | (a < 0)] = 0
        cell_km2 = abs(src.transform.a * src.transform.e) / 1e6
        a /= cell_km2
        st = src.window_transform(win)
        x0, y0, x1, y1 = transform_bounds("EPSG:4326", "EPSG:3857", *g.bounds)
        res = max(40.0, max(x1 - x0, y1 - y0) / max_px)
        nx, ny = max(1, int(np.ceil((x1 - x0) / res))), max(1, int(np.ceil((y1 - y0) / res)))
        dt = rasterio.transform.from_origin(x0, y1, res, res)
        dst = np.zeros((ny, nx), "float32")
        reproject(a, dst, src_transform=st, src_crs=src.crs, dst_transform=dt, dst_crs="EPSG:3857", resampling=Resampling.average)
    gm = transform_geom("EPSG:4326", "EPSG:3857", shapely.geometry.mapping(g))
    outside = geometry_mask([gm], out_shape=(ny, nx), transform=dt)
    rgba = np.zeros((ny, nx, 4), "uint8")
    for lo, col in zip(POP_CLASSES, POP_COLORS):
        m = (dst >= lo) & ~outside
        rgba[m] = [int(col[i:i + 2], 16) for i in (1, 3, 5)] + [235]
    outdir.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, "RGBA").save(outdir / f"{kid}.png", optimize=True)
    from pyproj import Transformer
    tr = Transformer.from_crs(3857, 4326, always_xy=True)
    xe, ye = x0 + nx * res, y1 - ny * res
    corners = [tr.transform(x0, y1), tr.transform(xe, y1), tr.transform(xe, ye), tr.transform(x0, ye)]
    return [[round(x, 6), round(y, 6)] for x, y in corners]


def one(args):
    cfg, kid, wkb, outdir = args
    g = shapely.make_valid(shapely.from_wkb(wkb))
    try:
        f = khg_features(cfg, kid, g)
    except Exception as e:
        return kid, None, None, f"layers: {type(e).__name__}: {e}"
    try:
        c = pop_png(cfg, kid, g, Path(outdir) / "khg_tiles" / "pop")
    except Exception as e:
        return kid, f, None, f"pop: {type(e).__name__}: {e}"
    return kid, f, c, None


def run(cfg, khg=None, workers=3):
    out = Path(cfg["out"])
    k = P.load_khg(cfg)
    k = k[k.khg_id.notna()]
    ids = k["khg_id"].tolist()
    todo = [(cfg, kid, shapely.to_wkb(geom), str(out)) for kid, geom in zip(ids, k.geometry.values) if not khg or kid in khg]
    print(f"{len(todo)} KHG", flush=True)
    feats, corners, errs = {}, {}, []
    with ProcessPoolExecutor(workers) as ex:
        for i, (kid, f, c, e) in enumerate(ex.map(one, todo, chunksize=1), 1):
            if e:
                errs.append((kid, e))
            for layer, rows in (f or {}).items():
                feats.setdefault(layer, []).extend(rows)
            if c:
                corners[kid] = c
            if i % 50 == 0 or i == len(todo):
                print(f"{i}/{len(todo)}", flush=True)
    src = out / "tiles" / "src"
    src.mkdir(parents=True, exist_ok=True)
    if not khg:
        for f in src.glob("x_*.geojsonl"):
            f.unlink()
        for layer, rows in feats.items():
            (src / f"{layer}.geojsonl").write_text("\n".join(json.dumps(r, separators=(",", ":")) for r in rows) + "\n", encoding="utf-8")
    else:          # a subset: replace those KHG's features in the existing files
        for layer in set(feats) | {f.stem for f in src.glob("x_*.geojsonl")}:
            p = src / f"{layer}.geojsonl"
            old = [ln for ln in (p.read_text(encoding="utf-8").splitlines() if p.exists() else []) if ln and json.loads(ln)["properties"]["k"] not in khg]
            p.write_text("\n".join(old + [json.dumps(r, separators=(",", ":")) for r in feats.get(layer, [])]) + "\n", encoding="utf-8")
    ip = out / "khg_tiles" / "pop" / "index.json"
    idx = json.loads(ip.read_text(encoding="utf-8")).get("corners", {}) if ip.exists() and khg else {}
    idx.update(corners)
    ip.parent.mkdir(parents=True, exist_ok=True)
    ip.write_text(json.dumps({"classes": POP_CLASSES, "colors": POP_COLORS, "unit": "people per km2", "source": str(cfg.get("final", {}).get("inputs_layers", {}).get("population")),
                              "corners": idx}, separators=(",", ":")), encoding="utf-8")
    print(f"layers: {', '.join(f'{k} {len(v)}' for k, v in sorted(feats.items()))}; population images {len(corners)}; errors {len(errs)}")
    for e in errs[:10]:
        print("  ", *e)
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--khg", nargs="*")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args(argv)
    cfg = copy.deepcopy(P.DEFAULTS)
    P._merge(cfg, yaml.safe_load(Path(a.config).read_text(encoding="utf-8")))
    cfg = P._expand(cfg)
    run(cfg, set(a.khg) if a.khg else None, a.workers)


if __name__ == "__main__":
    main()
