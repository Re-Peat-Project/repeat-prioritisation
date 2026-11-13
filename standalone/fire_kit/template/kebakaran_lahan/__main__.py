"""Burned area and hotspots by land status (concession, forest area, DMPG village, peat) for Indonesia or part of it.

    python -m kebakaran_lahan --config config.yaml                       all steps, all of Indonesia
    python -m kebakaran_lahan --config config.yaml --province Riau       one province (quick test)
    python -m kebakaran_lahan --config config.yaml --steps check         only check the inputs
    python -m kebakaran_lahan --config config.yaml --steps tables export rebuild the tables and the package from the last tally

Steps: check (inputs and fields), tally (30 m grid, cached per 90 km tile, resumes after an interruption), tables (summary
tables, checks, summary layers), export (one folder with CSV, Excel, layers and a data dictionary, and its zip).
"""
import argparse
import json
import logging
import sys
import time
from pathlib import Path

import pyogrio
import yaml

from . import fire_export as E
from . import fire_landstatus as F
from . import fire_tables as T

log = logging.getLogger("kebakaran_lahan")
STEPS = ["check", "tally", "tables", "export"]
NEED = {"villages": ["PULAU", "PROV_2023", "KABKO_2023"], "khg": ["NAMA_KHG"], "forest_area": ["Fungsi"], "licences": ["IZIN_USAHA"],
        "dmpg": [], "burned": [], "modis": ["acq_date|month", "level|confidence"], "viirs": ["acq_date", "confidence"]}


def load(path):
    """The kit's config.yaml as the config the tally modules read. Relative paths are relative to the config file's folder;
    input files are relative to `data`."""
    path = Path(path).resolve()
    c = yaml.safe_load(path.read_text(encoding="utf-8"))
    here = path.parent
    rel = lambda p: p if Path(p).is_absolute() else (here / p).resolve()          # noqa: E731
    data, inp, st = rel(c["data"]), c["inputs"], c.get("settings") or {}
    fl = {"years": c["years"], "villages": inp["villages"], "modis": inp["modis"], "viirs": list(inp["viirs"])}
    fl.update({k: st[k] for k in ("crs", "cell_m", "tile_cells", "static_radius_m") if k in st})
    if inp.get("dmpg_layer"):
        fl["dmpg_layer"] = inp["dmpg_layer"]
    cfg = {"data": str(data), "out": str(rel(c["out"])), "registry": str(rel(c["registry"])) if c.get("registry") else None,
           "inputs": {k: inp[k] for k in ("khg", "forest_area", "licences", "dmpg", "burned")}, "fire_landstatus": fl}
    peat = inp["peat"]
    if str(peat).lower().endswith((".tif", ".tiff", ".vrt")):
        cfg["peat"] = {"extent": str(data / peat)}
    else:
        fl["peat_vector"] = {"path": peat, "where": inp.get("peat_where"), "layer": inp.get("peat_layer")}
    return cfg


def check(cfg):
    """Every input exists and has the fields the tally reads; the burned-area file has a BA_<year> field for every year."""
    data, s, bad = Path(cfg["data"]), F.settings(cfg), []
    files = {**{k: cfg["inputs"][k] for k in ("khg", "forest_area", "licences", "dmpg", "burned")}, "villages": s["villages"], "modis": s["modis"]}
    files.update({f"viirs {n + 1}": f for n, f in enumerate(s["viirs"])})
    pv = s.get("peat_vector")
    files["peat"] = pv["path"] if pv else cfg["peat"]["extent"]
    for k, f in files.items():
        p = data / f
        if not p.exists():
            bad.append(f"{k}: file not found: {p}")
            continue
        if k == "peat" and not pv:
            continue
        try:
            info = pyogrio.read_info(p, layer=s.get("dmpg_layer", "dmpg_villages") if k == "dmpg" else (pv or {}).get("layer") if k == "peat" else None)
        except Exception as e:                      # noqa: BLE001
            bad.append(f"{k}: cannot read {p.name}: {e}")
            continue
        have = {x.lower() for x in info["fields"]}
        need = NEED.get(k.split()[0], [])
        if k == "burned":
            need = [f"BA_{y}" for y in range(s["years"][0], s["years"][1] + 1)]
        for n in need:
            if not any(alt.lower() in have for alt in n.split("|")):
                bad.append(f"{k}: field {n.replace('|', ' or ')} missing in {p.name} (fields: {', '.join(info['fields'])})")
        log.info("%-12s %s: %s features", k, p.name, f"{info['features']:,}")
    if bad:
        sys.exit("Input check failed:\n  " + "\n  ".join(bad))
    log.info("inputs OK")


def tiles_in(cfg, province=None, bbox=None):
    """Tiles (i_j) that cover a province (PROV_2023, as written in the village file) or a lon/lat box; None = all."""
    if not (province or bbox):
        return None
    from pyproj import Transformer
    import shapely
    s = F.settings(cfg)
    if province:
        v = pyogrio.read_dataframe(Path(cfg["data"]) / s["villages"], columns=["PROV_2023"], where=f"PROV_2023 = '{province}'")
        if not len(v):
            names = pyogrio.read_dataframe(Path(cfg["data"]) / s["villages"], columns=["PROV_2023"], read_geometry=False)["PROV_2023"].unique()
            sys.exit(f"province {province!r} not in the village file; names: {', '.join(sorted(map(str, names)))}")
        bbox = v.total_bounds
    tf = Transformer.from_crs(4326, s["crs"], always_xy=True)
    x0, y0 = tf.transform(bbox[0], bbox[1])
    x1, y1 = tf.transform(bbox[2], bbox[3])
    area = shapely.box(x0, y0, x1, y1)
    all_tiles, origin = F.tiles(cfg)
    c, t = s["cell_m"], s["tile_cells"]
    return [f"{i}_{j}" for i, j in all_tiles if shapely.box(*F.tile_geo(origin, i, j, c, t)[1]).intersects(area)]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m kebakaran_lahan", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--steps", nargs="*", default=STEPS, choices=STEPS)
    ap.add_argument("--workers", type=int, default=4, help="tiles computed in parallel; lower it if memory runs out")
    ap.add_argument("--province", help="only the tiles that cover this province (as written in PROV_2023)")
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("LON0", "LAT0", "LON1", "LAT1"), help="only the tiles that cover this box")
    ap.add_argument("--force", action="store_true", help="recompute tiles that are already in the cache")
    ap.add_argument("--no-rasters", action="store_true", help="do not write the 30 m status rasters")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    cfg = load(a.config)
    t0 = time.time()
    if "check" in a.steps:
        check(cfg)
    sel = tiles_in(cfg, a.province, a.bbox)
    if sel is not None:
        log.info("%d tiles cover the selection", len(sel))
    if "tally" in a.steps:
        F.run(cfg, a.workers, a.force, sel, rasters=not a.no_rasters)
    if "tables" in a.steps:
        T.run(cfg)
    if "export" in a.steps:
        src = Path(cfg["out"]) / "fire_landstatus"
        meta = json.loads((src / "meta.json").read_text(encoding="utf-8"))
        dest = E.export(src, Path(cfg["out"]) / f"paket_kebakaran_lahan_{meta['viirs_last']}", rasters=not a.no_rasters, data_dir=Path(cfg["data"]))
        log.info("package: %s", E.zip_dir(dest))
    log.info("done in %.0f min", (time.time() - t0) / 60)


if __name__ == "__main__":
    main()
