#!/usr/bin/env python3
"""Vector tiles of the dashboard map layers: one PMTiles archive per profiled KHG.

  repeat-national-tiles --config configs/examples/national_profile.yaml [--khg KHG.16.02.01 ...] [--workers 4] [--force] [--combined]

`repeat-national-dashboard` writes one GeoJSON-lines file per layer to <out>/tiles/src/ (burn, peat, outline, canal_p, canal_s,
canal_t, forest, feg, licence, ring, village, dmpg); every feature carries `k`, the khg_id. This command splits them by KHG and
turns each KHG into <out>/khg_tiles/<khg_id>.pmtiles with tippecanoe (pinned in tiles/Dockerfile; build the image once with
`docker build -t repeat-tippecanoe:2.79.0 repeat-prioritisation/tiles`). One file per KHG keeps every file far below the 100 MB
limit of GitHub and lets the page load only the KHG on screen. A KHG is skipped when its archive is newer than the sources
(resumable); `--force` redoes it. No feature is dropped and tiles have no size limit; lines and polygons are thinned only to the
pixel of each zoom level. `--combined` writes the single archive <out>/khg_layers.pmtiles instead (for local use; it is too large for GitHub).
Serve the folder over HTTP (PMTiles reads byte ranges; a page opened as a file cannot).
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from repeat_prioritisation.national import profile as P

IMAGE = "repeat-tippecanoe:2.79.0"
MINZOOM, MAXZOOM = 6, 15    # a z15 tile holds 0.3 m coordinates; the page overzooms from there
FLAGS = ["--force", "-Z", str(MINZOOM), "-z", str(MAXZOOM), "--no-feature-limit", "--no-tile-size-limit", "--no-tiny-polygon-reduction",
         "--read-parallel", "--buffer", "16"]


def write_sources(src, feats):
    """One GeoJSON-lines file per layer; removes files of layers that no longer exist."""
    src = Path(src)
    src.mkdir(parents=True, exist_ok=True)
    for f in src.glob("*.geojsonl"):
        f.unlink()
    for layer, rows in feats.items():
        (src / f"{layer}.geojsonl").write_text("\n".join(json.dumps(r, separators=(",", ":")) for r in rows) + "\n", encoding="utf-8")


def sources(out_dir):
    src = Path(out_dir) / "tiles" / "src"
    files = sorted(src.glob("*.geojsonl"))
    if not files:
        raise SystemExit(f"no tile sources in {src}: run repeat-national-dashboard first")
    return src, files


def run_combined(out_dir, image=IMAGE):
    out_dir = Path(out_dir)
    src, files = sources(out_dir)
    target = out_dir / "khg_layers.pmtiles"
    cmd = ["docker", "run", "--rm", "-v", f"{src.resolve()}:/in:ro", "-v", f"{out_dir.resolve()}:/out", image,
           "-o", "/out/khg_layers.pmtiles", *FLAGS, *[a for f in files for a in ("-L", f"{f.stem}:/in/{f.name}")]]
    subprocess.run(cmd, check=True)
    print(f"{target}: {target.stat().st_size / 1e6:.1f} MB, layers {', '.join(f.stem for f in files)}")


def split_by_khg(src, files, only=None):
    """{khg_id: {layer: [GeoJSON lines]}} from the layer files (the `k` property of each feature is the khg_id)."""
    by = defaultdict(lambda: defaultdict(list))
    for f in files:
        with open(f, "rb") as fh:
            for line in fh:
                m = re.search(rb'"k":"([^"]+)"', line)
                if m and (not only or m.group(1).decode() in only):
                    by[m.group(1).decode()][f.stem].append(line)
    return by


def tile_one(out_dir, kid, layers, image):
    work = Path(out_dir) / "tiles" / "by_khg" / kid
    work.mkdir(parents=True, exist_ok=True)
    for layer, lines in layers.items():
        (work / f"{layer}.geojsonl").write_bytes(b"".join(lines))
    tmp = f"{kid}.tmp.pmtiles"
    out = Path(out_dir) / "khg_tiles"
    out.mkdir(parents=True, exist_ok=True)
    cmd = ["docker", "run", "--rm", "-v", f"{work.resolve()}:/in:ro", "-v", f"{out.resolve()}:/out", image, "-o", f"/out/{tmp}", *FLAGS,
           *[a for layer in layers for a in ("-L", f"{layer}:/in/{layer}.geojsonl")]]
    subprocess.run(cmd, check=True, capture_output=True)
    (out / tmp).replace(out / f"{kid}.pmtiles")          # a file is only ever complete or absent
    for f in work.glob("*"):
        f.unlink()
    work.rmdir()
    return kid


def run(out_dir, image=IMAGE, khg=None, workers=4, force=False):
    out_dir = Path(out_dir)
    src, files = sources(out_dir)
    newest = max(f.stat().st_mtime for f in files)
    by = split_by_khg(src, files, set(khg) if khg else None)
    todo = {k: v for k, v in by.items() if force or not (out_dir / "khg_tiles" / f"{k}.pmtiles").exists() or (out_dir / "khg_tiles" / f"{k}.pmtiles").stat().st_mtime < newest}
    print(f"{len(by)} KHG, {len(todo)} to tile", flush=True)
    if todo:
        with ThreadPoolExecutor(workers) as ex:
            for i, kid in enumerate(ex.map(lambda kv: tile_one(out_dir, kv[0], kv[1], image), sorted(todo.items(), key=lambda kv: -sum(len(x) for x in kv[1].values()))), 1):
                if i % 25 == 0 or i == len(todo):
                    print(f"{i}/{len(todo)}", flush=True)
    sizes = [f.stat().st_size for f in (out_dir / "khg_tiles").glob("*.pmtiles") if not f.name.endswith(".tmp.pmtiles")]
    print(f"{out_dir / 'khg_tiles'}: {len(sizes)} files, {sum(sizes) / 1e6:.0f} MB, largest {max(sizes) / 1e6:.1f} MB")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--image", default=IMAGE)
    ap.add_argument("--khg", nargs="*", help="khg_id to tile (default: all)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--force", action="store_true", help="tile KHG whose archive is up to date again")
    ap.add_argument("--combined", action="store_true", help="one archive for all KHG (khg_layers.pmtiles) instead of one per KHG")
    a = ap.parse_args(argv)
    cfg = copy.deepcopy(P.DEFAULTS)
    P._merge(cfg, yaml.safe_load(Path(a.config).read_text(encoding="utf-8")))
    out = P._expand(cfg)["out"]
    run_combined(out, a.image) if a.combined else run(out, a.image, a.khg, a.workers, a.force)


if __name__ == "__main__":
    main()
