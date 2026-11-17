#!/usr/bin/env python3
"""Indicators for the KHG of KLH's 337 that hold no peat in KLH's peat map, with the whole KHG taken as peat.

  repeat-national-final-whole-khg --config configs/examples/national_profile.yaml [--workers 2] [--skip-profile]

Amendment to the final prioritisation, 2026-11-17, written before any result for these KHG: the 10 KHG of KLH's 337 work list
with no LAHAN_GAMB peat in the PPEG analysis were left unscored. A KHG is delineated as a peat hydrological unit, and the
Global Peatland Map (1 km) shows peat over 33 to 100% of each of them, so they are scored with the whole KHG as the peat extent
and flagged `whole_khg` (peat extent not mapped by KLH; less reliable). They stay out of the scoring pool, so the percentile
ranks and tercile cuts of every other KHG do not change.

Steps, all into <out>/whole_khg/:
  1. the KHG: in the 337 (sites/khg_klh_priority.csv) with no KLH peat (ppeg/ppeg_khg.csv peat_ha 0 or missing)
  2. peat_whole_khg.vrt: KLH's 30 m peat raster (peat.extent) with each of these KHG burned in as peat (patches/*.tif)
  3. config.yaml: the national config with peat.extent pointing at that VRT and out at this folder
  4. operational/: repeat-national-profile --mode operational --only <these KHG> (fire and hotspot indicators on the peat)
  5. tenure_complexity/: repeat-national-tenure-complexity --khg <these KHG> (claim indicators; the index is computed by
     repeat-national-final against the main pool)
  6. final_inputs.csv: the per-KHG inputs of repeat-national-final-inputs on the whole-KHG peat, and PPEG land cover and volume
  7. ppeg_khg.csv: the PPEG sums of national.ppeg with the whole KHG counted as peat
repeat-national-final reads <out>/whole_khg/ when `final.score_337_without_klh_peat` is true.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import rasterio.features
import yaml
from rasterio.windows import from_bounds

from repeat_prioritisation.national import final_inputs as FI
from repeat_prioritisation.national import land as L
from repeat_prioritisation.national import ppeg as PG
from repeat_prioritisation.national import profile as P
from repeat_prioritisation.national.fire_common import peat_path

log = logging.getLogger("prioritas.whole_khg")
nm = lambda s: re.sub(r"\s+", " ", str(s)).strip()


def targets(cfg, hub):
    kp = pd.read_csv(hub / "sites" / "khg_klh_priority.csv")
    pp = pd.read_csv(Path(cfg["out"]) / "ppeg" / "ppeg_khg.csv")
    peat = pp[pp.khg_code.astype(str).str.startswith("KHG.")].groupby("khg_code").peat_ha.sum()
    k = kp[kp.klh_337.astype(bool)]
    return k[k.khg_code.map(peat).fillna(0) <= 0][["khg_code", "khg_name"]].reset_index(drop=True)


def build_vrt(src_path, khg, out):
    """VRT of the peat raster with the KHG polygons burned in as 1 (later sources win where they are not nodata)."""
    pdir = out / "patches"
    pdir.mkdir(parents=True, exist_ok=True)
    with rasterio.open(src_path) as src:
        prof, crs, T, nod = src.profile, src.crs, src.transform, int(src.nodata if src.nodata is not None else 255)
        W, H = src.width, src.height
        g = khg.to_crs(crs)
        srcs = []
        for r in g.itertuples():
            w0 = from_bounds(*r.geometry.bounds, transform=T)
            c0, r0 = int(np.floor(w0.col_off)) - 1, int(np.floor(w0.row_off)) - 1
            win = rasterio.windows.Window(c0, r0, int(np.ceil(w0.col_off + w0.width)) + 1 - c0, int(np.ceil(w0.row_off + w0.height)) + 1 - r0)
            wt = src.window_transform(win)
            arr = rasterio.features.rasterize([(r.geometry, 1)], out_shape=(int(win.height), int(win.width)), transform=wt, fill=nod, dtype="uint8")
            f = pdir / (re.sub(r"[^\w.-]", "_", r.khg_id) + ".tif")
            with rasterio.open(f, "w", driver="GTiff", width=int(win.width), height=int(win.height), count=1, dtype="uint8", crs=crs,
                               transform=wt, nodata=nod, compress="deflate") as dst:
                dst.write(arr, 1)
            srcs.append((f, win, int((arr == 1).sum())))
    gt = ", ".join(repr(x) for x in (T.c, T.a, T.b, T.f, T.d, T.e))
    def source(path, win, tag):
        w, h = int(win.width), int(win.height)
        return (f'    <{tag}><SourceFilename relativeToVRT="0">{Path(path).as_posix()}</SourceFilename><SourceBand>1</SourceBand>'
                f'<SrcRect xOff="0" yOff="0" xSize="{w}" ySize="{h}"/><DstRect xOff="{int(win.col_off)}" yOff="{int(win.row_off)}" xSize="{w}" ySize="{h}"/>'
                + (f"<NODATA>{nod}</NODATA>" if tag == "ComplexSource" else "") + f"</{tag}>")
    xml = [f'<VRTDataset rasterXSize="{W}" rasterYSize="{H}">', f"  <SRS>{crs.to_wkt().replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace(chr(34), '&quot;')}</SRS>",
           f"  <GeoTransform>{gt}</GeoTransform>", '  <VRTRasterBand dataType="Byte" band="1">', f"    <NoDataValue>{nod}</NoDataValue>",
           source(src_path, rasterio.windows.Window(0, 0, W, H), "SimpleSource")]
    xml += [source(f, w, "ComplexSource") for f, w, _ in srcs]
    xml += ["  </VRTRasterBand>", "</VRTDataset>"]
    vrt = out / "peat_whole_khg.vrt"
    vrt.write_text("\n".join(xml), encoding="utf-8")
    return vrt, {Path(f).stem: n for f, _, n in srcs}


def run(cmd):
    log.info("run: %s", " ".join(map(str, cmd)))
    r = subprocess.run([sys.executable, "-m", *map(str, cmd)], capture_output=True, text=True)
    if r.returncode:
        log.error(r.stdout[-3000:] + r.stderr[-3000:])
        raise SystemExit(f"failed: {cmd[0]}")
    return r


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--skip-profile", action="store_true", help="reuse operational/ from an earlier run")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    cfg = L.load_cfg(a.config)
    hub = Path(cfg.get("hub") or Path(cfg["registry"]).parents[1])
    out = Path(cfg["out"]) / "whole_khg"
    out.mkdir(parents=True, exist_ok=True)
    t = targets(cfg, hub)
    ids = t.khg_code.tolist()
    log.info("%d KHG of the 337 without KLH peat: %s", len(ids), ", ".join(ids))
    khg = P.load_khg(cfg)
    khg = khg[khg.khg_id.isin(ids)]
    vrt, cells = build_vrt(peat_path(cfg), khg, out)
    # derived config: the national config with the whole-KHG peat and this output folder
    raw = yaml.safe_load(Path(a.config).read_text(encoding="utf-8"))
    raw["peat"]["extent"] = vrt.as_posix()
    raw["out"] = out.as_posix()
    dcfg = out / "config.yaml"
    dcfg.write_text("# written by repeat-national-final-whole-khg: the national config with the whole-KHG peat extent\n"
                    + yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8")
    sub = L.load_cfg(dcfg)
    if not a.skip_profile:
        run(["repeat_prioritisation.national.profile", "--config", dcfg, "--mode", "operational", "--only", *ids, "--out", out])   # profile writes to <out>/operational
    run(["repeat_prioritisation.national.tenure_complexity", "--config", dcfg, "--khg", *ids, "--workers", a.workers, "--force"])
    rows = [FI.one(sub, r.khg_id, r.nama, r.geometry) for r in khg.itertuples()]
    fi = pd.DataFrame(rows)
    names = [nm(x) for x in t.khg_name]
    vol = FI.peat_volume(Path(cfg["data"]), whole_khg=names)
    fi = fi.merge(vol.assign(_k=vol.NAMA_KHG.map(lambda s: nm(s).casefold())).drop(columns="NAMA_KHG"),
                  left_on=fi.khg.map(lambda s: nm(s).casefold()), right_on="_k", how="left").drop(columns=["_k", "key_0"], errors="ignore")
    fi.to_csv(out / "final_inputs.csv", index=False, float_format="%.10g")
    data = Path(cfg["data"])
    tg = PG.village_keys(data / PG.VILLAGES)
    f, side = PG.load(data / PG.NAME, tg, whole_khg=names)
    pp = PG.summarise(f, side, hub / "sites" / "khg_registry.csv")
    pp[pp.khg_code.isin(ids)].to_csv(out / "ppeg_khg.csv", index=False)
    (out / "whole_khg.json").write_text(json.dumps({"khg": ids, "peat_cells_30m": cells, "vrt": vrt.as_posix(),
                                                   "rule": "amendment 2026-11-17: whole KHG as peat for the 337 without KLH peat"}, indent=1), encoding="utf-8")
    log.info("-> %s", out)


if __name__ == "__main__":
    main()
